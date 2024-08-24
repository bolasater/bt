from __future__ import annotations 
from enum import Enum
import dataclasses
from typing import Optional, Union
from pathlib import Path
import math
import random
import json
import shapely
from shapely.geometry import Point, LineString, Polygon
from shapely import STRtree

DB_LEVEL = 1 # the higher the level, the more verbose. Level 0 turns it off.
def db(lvl,msg):
    if lvl <= DB_LEVEL:
        print(msg)

AttackType = Enum('AttackType',['aoe','missile','melee']) #used for display
Action = Enum('Action',['idle','shoot','hurt','slash','spellcast','thrust','walk'])
# use first frame of walk for 'idle', if needed.
AoEGeom = Enum('AoEGeom',['hex','cone','square'])

class AoEStats: 
    """Stats unique to AoE attacks"""
    unit_hexagon = Polygon([
        (round(math.cos(i*math.pi/3),3),
         round(math.sin(i*math.pi/3),3))
         for i in range(6)])
    unit_cone = Polygon([(0,0),(-.5,1),(.5,1)])
    unit_square = Polygon([(.5,.5),(-.5,.5),(-.5,-.5),(.5,-.5)])
    def __init__(self, geom:AoEGeom, r:float) -> None:           
        self.geom = geom
        self.r = r

    def init_from_dict(vals_dict )->AoEStats:
        return AoEStats(
            AoEGeom[vals_dict["geom"]],
            vals_dict["radius"])
        
class MissileStats:
    """Stats unique to missile attacks"""
    def __init__(self,
                 missile_speed: float, # speed of missile in m/s.
    )->None:
        self.missile_speed = missile_speed

    def init_from_dict(vals_dict )->MissileStats:
        return MissileStats(vals_dict["missile_speed"])

class AttackStats:
    """Holds unique characteristics of each attack"""
    def __init__(self,
                 atk_type:AttackType,
                 dmg_fraction: float, # %of mob dmg attack delivers
                 rng: float,
                 atks_sec: float,
                 cool_down: float,
                 launch_ratio: float, # % of action complete when missile leaves or dmg is dealt
                 addl_stats:Optional[Union[AoEStats,MissileStats]] = None,
                 ) -> None:    
        self.atk_type: AttackType = atk_type
        self.dmg_fraction = dmg_fraction
        self.atks_sec = atks_sec
        self.rng = rng
        self.cool_down = cool_down
        self.cool_down_timer = 0.0
        self.launch_ratio = launch_ratio
        self.dmg_atk = None #can't be computed now 
        self.addl_stats = addl_stats

        if atks_sec <= 0.0:
            raise ValueError(f"atks_sec must be positive: {atks_sec}")
        self.secs_atk = 1/atks_sec
        valid_type = ((type(addl_stats) == MissileStats and atk_type == AttackType.missile) or 
                        (type(addl_stats) == AoEStats and atk_type == AttackType.aoe) or
                        (addl_stats is None and atk_type == AttackType.melee))
        if not valid_type:
            raise ValueError(f'Attack Type {atk_type.name} does not match addl_stats type {type(addl_stats)}')

    def init_from_dict(vals_dict )->AttackStats:
        atk_type = AttackType[vals_dict["atk_type"]]
        addl_stats_raw = vals_dict.get("addl_stats")
        if atk_type == (AttackType.aoe or AttackType.missile):
            if addl_stats_raw is None:
                raise ValueError(f"Addl_stats must exist for AttackType {atk_type.name}")
        addl_stats = None
        if atk_type == AttackType.aoe:
            addl_stats = AoEStats.init_from_dict(addl_stats_raw) 
        elif atk_type == AttackType.missile:
            addl_stats = MissileStats.init_from_dict(addl_stats_raw)
        return AttackStats(
            atk_type,
            vals_dict["dmg_fraction"],
            vals_dict["rng"],
            vals_dict["atks_sec"],
            vals_dict["cool_down"],
            vals_dict["launch_ratio"],
            addl_stats
        )

class MobTypeModel:
    """Holds immutable aspects for Mobs."""

    r: float = .05 #growth rate for all curves
    dps_health_ratio = .1 #avg % of health a hit should take
    starting_health = 100
    dying_time = 2 #time of death cycle. Not strictly model but needs to be here.

    @classmethod
    def power_curve(cls, level):
        r = cls.r
        return ((1 + r)**level)/(1 + (1 + r)**level)
    
    def __init__(self, 
                 name: str,
                 dmg_health_split: float, #0<>1, % of power allocated to dps vs health
                 mvt: float, #
                 atk_stats_dict: dict[Action,AttackStats] #dict of available attacks w/ ranges in meters and attacks per second  
                 ) -> None:
        self.name = name
        self.dmg_health_split = dmg_health_split
        self.mvt = mvt
        self.atk_stats_dict = atk_stats_dict

    def init_from_dict(name, vals_dict)->MobTypeModel:
        atk_stats_dict_raw = vals_dict["atk_stats_dict"]
        atk_stats_dict = {}
        for k,v in atk_stats_dict_raw.items():
            atk_stats = AttackStats.init_from_dict(v) if v is not None else None
            atk_stats_dict[Action[k]] = atk_stats
        return MobTypeModel(
            name,
            vals_dict["dmg_health_split"],
            vals_dict["mvt"],
            atk_stats_dict
        )

    def health(self,level):
        return MobTypeModel.power_curve(level) * (1 - self.dmg_health_split)*MobTypeModel.starting_health
    
    def dps(self, level):
        return MobTypeModel.power_curve(level) * self.dmg_health_split * MobTypeModel.dps_health_ratio * MobTypeModel.starting_health
    
class MobModel:
    """Actual moving objects.  The have a MobModelType"""
    id_counter = 0

    @classmethod
    def angle_to_point(cls, a:Point,b:Point)->float:
        dist = a.distance(b)
        nd = [1/dist*i for i in (b.x - a.x, b.y - a.y)]
        #length = (nd[0]**2 + nd[1]**2)**.5 
        #theta = match.acos(norm_diff[])
        theta = math.acos(abs(nd[0]))
        if nd[0]>=0:
            theta = theta if nd[1]>= 0 else math.pi * 2 - theta
        else:
            theta = math.pi - theta if nd[1]>=0 else math.pi + theta    
        return theta
    
    @classmethod
    def angle_of_target_vector(cls, a:Point, v:Optional[tuple[float,float]])->float:
        if v is None:
            return 0.0
        dist = (v[0]**2 + v[1]**2)**.5 
        nd = [1/dist*i for i in (v.x - a.x, v.y - a.y)]
        theta = math.acos(abs(nd[0]))
        if nd[0]>=0:
            theta = theta if nd[1]>= 0 else math.pi * 2 - theta
        else:
            theta = math.pi - theta if nd[1]>=0 else math.pi + theta    
        return theta
        
    def __init__(self, 
                 mob_type_model,
                 level,
                 team_idx:int, 
                 x:float, y:float) -> None:
        self.id = MobModel.id_counter
        MobModel.id_counter +=1

        #Core characteristics
        self.mobTypeModel = mob_type_model
        if mob_type_model is None:
            raise ValueError("The mob type model must be valid before a mob model is initialized")
        self.level = level
        self.team_idx = team_idx
        self.max_health = mob_type_model.health(level)
        self.health = self.max_health
        self.dps = mob_type_model.dps(level)
        self.atk_stats_dict = mob_type_model.atk_stats_dict
        self.mvt = mob_type_model.mvt

        #Current status tracking
        self.action = Action.idle
        self.posn = Point(x,y)
        self.is_action_done = True
        self.is_alive = True
        self.enemy = None
        self.target_vector = None #Either None or unit vector to target
        self.has_shot = False #used in atks to determine dmg transfer or projectile launch
        self.action_timer = 0.0 #records how long an action is taking
        self.affected_enemies = []
        #self.spell_geom:Optional[Polygon] = None #stores spell aoe, when this mob casts one

        #pre-compute other atk_stats from core stats
        for a,stats in self.atk_stats_dict.items():
            stats.dmg_atk = self.dps * stats.dmg_fraction/stats.atks_sec

    def update(self, game_model, delta_time):
        """
        Called once a turn, 'update' manages mob position, target and action. Delta_time is how much time since last update.
        """
        db(4,f'    Mob {self.id} is doing {self.action.name}.')

        if self.is_action_done:
            self.determine_next_action_and_target(game_model)
            if self.action != Action.walk:
                db(3,f'    Mob {self.id} starts to {self.action.name}. Action_timer:{round(self.action_timer,3)}, target dist.: {round(self.posn.distance(self.enemy.posn),2)}.')
                db(4,f'          action_timer:{round(self.action_timer,3)}')
        
        if self.action is None:
            raise ValueError("Action should exist here.")
        if self.action == Action.hurt:
            raise ValueError("Dying units should be handled in separate list.")

        #update cooldown timers
        for a,stats in self.atk_stats_dict.items():
            if self.action != a:
                stats.cool_down_timer = max(stats.cool_down_timer - delta_time,0.0)

        # keep action done so that choice gets re-evaluated
        if self.action == Action.idle:
            return

        if self.action == Action.walk:
            target_dist = self.posn.distance(self.enemy.posn) -  game_model.min_dist
            travel_dist = self.mvt*delta_time
            dist = min(target_dist,travel_dist)
            self.posn = Point(self.posn.x + dist*self.target_vector[0], self.posn.y + dist*self.target_vector[1])
            return
       
        #Update action timer.  Note, no need to do it if action is walk, hurt or idle
        self.action_timer += delta_time

         #Can assume action is attack.  'Hurt' handled separately.
        atk_stats = self.atk_stats_dict[self.action]
        secs_atk, launch_ratio = atk_stats.secs_atk, atk_stats.launch_ratio         

        db(4,f'          Mob {self.id}- action_timer:{round(self.action_timer,3)}')
        if self.action_timer >= launch_ratio*secs_atk  and not self.has_shot:
            self.start_attack_effects(game_model)
            self.has_shot = True

        if self.action_timer > secs_atk:
            if not self.has_shot: #timer possibly jumped past mid point of action
                self.start_attack_effects(game_model)
                self.has_shot = True
            db(3,f'    Mob {self.id} is done with {self.action.name}.')
            self.is_action_done = True

    def start_attack_effects(self,game_model:GameModel)->None:
        atk_stats = self.atk_stats_dict[self.action]
        dmg_atk = atk_stats.dmg_atk 
        match atk_stats.atk_type:
            case AttackType.missile:
                missile_speed = atk_stats.addl_stats.missile_speed
                game_model.shooting.append((self,self.enemy,missile_speed))
                game_model.being_hit.append((self.enemy,3))
                self.enemy.health -= dmg_atk
                db(2,f'    HIT! Mob {self.id} just hit mob {self.enemy.id} with missile for {round(dmg_atk,2)} leaving {round(self.enemy.health,2)}.')
            case AttackType.aoe:
                self.cast_spell(game_model,atk_stats)
                for enemy in self.affected_enemies:
                    game_model.being_hit.append((enemy,3))
                    enemy.health -= dmg_atk
                    db(2,f'    HIT! Mob {self.id} just hit mob {self.enemy.id} with spell for {round(dmg_atk,2)} leaving {round(self.enemy.health,2)}.')
                self.affected_enemies = []
            case AttackType.melee:
                game_model.being_hit.append((self.enemy,3))
                self.enemy.health -= dmg_atk
                db(2,f'    HIT! Mob {self.id} just hit mob {self.enemy.id} with melee attack for {round(dmg_atk,2)} leaving {round(self.enemy.health,2)}.')

    def cast_spell(self,game_model:GameModel, atk_stats:AttackStats)->None: 
        """Determines affected enemies of spell"""
        aoe_stats = atk_stats.addl_stats
        geom_type = aoe_stats.geom
        r = aoe_stats.r
        geom = None
        match geom_type:
            case AoEGeom.hex:
                geom = AoEStats.unit_hexagon
                geom = shapely.affinity.scale(geom,r,r)
                theta = self.angle_to_point(self.posn,self.enemy.posn)
                geom = shapely.affinity.rotate(geom,theta)
                geom = shapely.affinity.translate(geom,self.enemy.posn.x,self.enemy.posn.y)
            case AoEGeom.cone:
                geom = AoEStats.unit_cone
                geom = shapely.affinity.scale(geom,r,3*r)
                theta = self.angle_of_target_vector(self.posn,self.target_vector)
                geom = shapely.affinity.rotate(geom,theta) 
                geom = shapely.affinity.translate(geom,self.enemy.posn.x,self.enemy.posn.y)
            case AoEGeom.square:
                geom = AoEStats.unit_square
                geom = shapely.affinity.scale(geom,r,r)
                theta = self.angle_to_point(self.posn,self.target_vector)
                geom = shapely.affinity.rotate(geom,theta)
                geom = shapely.affinity.translate(geom,self.enemy.posn.x,self.enemy.posn.y)
        
        game_model.spell_geoms.append((geom,4))
        self.get_affected_enemies(game_model,geom)

    def get_closest_enemy(self,game_model)->MobModel: #returns MobModel
        return game_model.get_closest_enemy(self)
    
    def get_affected_enemies(self,game_model: GameModel, geom:Polygon):
        self.affected_enemies = game_model.get_affected_enemies(self, geom)

    def determine_next_action_and_target(self, game_model)->tuple[Action,Optional[MobModel],Optional[tuple[float,float]]]: #returns triple of action, enemy, vector
        enemy = self.get_closest_enemy(game_model)
        if enemy is None:
            self.target_vector = None
            self.action = Action.idle
            return
            # raise ValueError("If no enemies left, then game should have already ended.")
        if type(self) != type(enemy):
            raise ValueError("enemy is not a MobModel.")
        db(4,f'{type(enemy.posn)}:{enemy.posn}')
        dist = self.posn.distance(enemy.posn)
        next_atk = None
        best_rng = 9999
        for a,stats in self.atk_stats_dict.items():
            rng = stats.rng
            if (dist <= rng and rng <= best_rng):
                next_atk = a
                best_rng = rng
                db(3,f'          {next_atk.name} chosen. Rng: {rng}, dist: {round(dist,2)}')
        self.action = Action.walk if next_atk is None else next_atk
        self.enemy = enemy
        self.action_timer = 0.0
        self.has_shot = False
        if self.action != Action.walk:
            self.is_action_done = False
        self.set_target_vector()
    
    def set_target_vector(self): #used in walking and shooting, 1 meter in lth, unless None
        if self.enemy is None:
            self.target_vector = None
        else:
            (x,y) = (self.enemy.posn.x -self.posn.x,self.enemy.posn.y -self.posn.y )
            dist = self.posn.distance(self.enemy.posn)
            if dist < .5:
                return None
            else:
                self.target_vector = (x/dist,y/dist)
            
    def start_dying(self): 
        """Special action called by GameModel at proper time in high-level update."""
        self.action_timer = 0.0
        self.action = Action.hurt
        self.is_action_done = False
        self.is_alive = False
    
    def die(self, delta_time):
        """ Die is handled specially so that it doesn't effect the simulation.  Main purpose is for view object to animate properly."""    
        self.action_timer += delta_time
        if self.action_timer > MobTypeModel.dying_time:
            self.is_action_done = True
        return self.is_action_done
            
class GameModel():
    min_dist = 1 #the closest Mobs can get to each other in meters.
   
    def __init__(self) -> None:
        """Game Model runs the game.  It manages teams, victory conditions, geometric searches."""
        # Quantities that don't get reset between runs
        self.mob_types = {}
        self.field_dims = [50,50] #wd, ht in meters
        self.root_data_path = Path('.') / 'data'
        # State that does get reset
        #   Lists of combatants and STRtrees for doing geometric searches
        self.game_time = 0.0
        self.teams = [[],[]]
        self.strtrees = [None,None]
        #   Lists to track certain mob actions
        self.shooting = [] #triple of shooter,target, and count
        self.being_hit = [] #double of victim and count
        self.spell_geoms = [] #shows areas of effect (geom, count)
        self.dying = [] #list to manage death animations (important for view)
        #   End game tracking
        self.winner = 3
        self.game_over = False #checked by view

        self.load_mob_types_from_file()

    def reset(self): #reset variables for a new game run
        self.game_time = 0.0
        self.teams = [[],[]]
        self.strtrees = [None,None]
        self.shooting = []
        self.being_hit = [] 
        self.spell_geoms = [] 
        self.dying = []
        self.winner = 3
        self.game_over = False 

    def setup(self, input_dict=None):
        self.reset()
        if input_dict == None:
            self.load_mobs_from_file()
        else:
            self.load_mobs_from_dict(input_dict)
           
    def load_mob_types_from_file(self, json_file = 'mob_types.json'): #set up MobTypeModels here, Always uses json for mob models
        with open((self.root_data_path / json_file).as_posix()) as f:
            data = json.load(f)
            f.close()

        mob_types_data = data["mob_types"]
        for k,v in mob_types_data.items():
            self.mob_types[k] = MobTypeModel.init_from_dict(k,v)

    def load_mobs_from_file(self,json_file = 'mobs.json'):
        """Called once after initialization.  Mob model creation happens here. Assumes (for now) mobs in 'mobs.json'"""
        with open((self.root_data_path / json_file).as_posix()) as f:
            data = json.load(f)
            f.close()
        mobs_dict = data
        # mobs_dict = {}
        # mobs_dict["teams"] = data["teams"]
        # mobs_dict["level"] = data["level"]
        # mobs_data = data["mobs"]
        self.load_mobs_from_dict(mobs_dict)
        # for md in mobs_data:
        #     team_idx = md['team']
        #     f_wd,f_ht = self.field_dims
        #     self.teams[team_idx].append(MobModel(
        #         self.mob_types[md['mob_type']],
        #         md['level'],
        #         team_idx,
        #         (team_idx*.5)*f_wd + .4*f_wd*random.random(),
        #         .25*f_ht + .75*f_ht*random.random()
        #      ))
        db(4,f'{[[(m.id,m.team_idx, round(m.posn.x,1),round(m.posn.y,1), round(m.health,1),round(m.dps,1)) for m in t if m.is_alive]for t in self.teams]}')

    def load_mobs_from_dict(self, input_dict):
        """Called once after initialization.  Mob model creation happens here. Assumes (for now) mobs in 'mobs.json'"""
        f_wd,f_ht = self.field_dims
        level = input_dict['level']
        for i,(tn,arch_dict) in enumerate(input_dict['teams'].items()):
            team_idx = i
            for an,ct in arch_dict.items():
                for c in range(ct):
                    self.teams[team_idx].append(MobModel(
                        self.mob_types[an],
                        level,
                        team_idx,
                        (team_idx*.5)*f_wd + .4*f_wd*random.random(),
                        .25*f_ht + .75*f_ht*random.random()
                    ))
        db(4,f'{[[(m.id,m.team_idx, round(m.posn.x,1),round(m.posn.y,1), round(m.health,1),round(m.dps,1)) for m in t if m.is_alive]for t in self.teams]}')

    def update(self, delta_time):
        """Called once per turn"""
        self._update_teams_and_trees()
        self.winner = self.check_for_victory()
        self.game_over = (self.winner != 3)

        # temp_dying = self.dying.copy() #make copy to avoid pop side effects
        for i,m in enumerate(self.dying):
            if m.die(delta_time):
               db(3,f'Mob {m.id} finished dying.')
               self.dying.pop(i)

        for i,(s,t,c) in enumerate(self.shooting):
            self.shooting[i] = (s,t,c-1)

        for i,(s,t,c) in enumerate(self.shooting):
            if c<=0:
                self.shooting.pop(i)
        
        for i,(t,c) in enumerate(self.being_hit):
            self.being_hit[i] = (t,c-1)

        for i,(t,c) in enumerate(self.being_hit):
            if c<=0:
                self.being_hit.pop(i)       

        for i,(g,c) in enumerate(self.spell_geoms):
            self.spell_geoms[i] = (g,c-1)

        for i,(g,c) in enumerate(self.spell_geoms):
            if c<=0:
                self.spell_geoms.pop(i)    

        #results should be as if everything happens simulataneously
        neither_team_is_empty = 1
        for t in self.teams:
            neither_team_is_empty *= len(t)

        # if neither_team_is_empty: #need to check this bc MobModel update logic requires both teams to have enemies
        for t in self.teams:
            for i,m in enumerate(t):
                m.update(self,delta_time)
        # ... so check for death after all teams update
        for t in self.teams:
            for i,m in enumerate(t):
                if m.health <= 0:
                    self.dying.append(m)
                    db(3,f'Mob {m.id} started dying.')
                    m.start_dying()

    def check_for_victory(self):
        """ Should be called in update.  
            0 = team 0, 
            1= team 1, 
            2 = tie,
            3 = no victory yet """
        if len(self.dying) > 0: # let everyone finish dying
            return 3
        team_dead_list = [True if len(tree)==0 else False for tree in self.strtrees]
        if len(team_dead_list) != 2:
            raise ValueError("There should be exactly 2 teams!")
        dead_0,dead_1 = tuple(team_dead_list)
        if dead_0:
            return 1 if not dead_1 else 2
        return 0 if dead_1 else 3

    # Helper functions for mob strategies
    def get_closest_enemy(self,mob_model:MobModel)->MobModel: 
        enemy_team_idx = 1 if mob_model.team_idx == 0 else 0
        enemies, enemy_STRtree = self.teams[enemy_team_idx], self.strtrees[enemy_team_idx]
        enemy_idx = enemy_STRtree.nearest(mob_model.posn)
        # enemy_STRtree.query()
        return enemies[enemy_idx] if enemy_idx is not None else None

    def get_affected_enemies(self,mob_model:MobModel,geom:Polygon)->list[MobModel]:
        enemy_team_idx = 1 if mob_model.team_idx == 0 else 0
        enemies, enemy_STRtree = self.teams[enemy_team_idx], self.strtrees[enemy_team_idx]
        enemy_idcs = enemy_STRtree.query(geom)
        return [enemies[i] for i in enemy_idcs] #can be empty

    def _update_teams_and_trees(self):
        "teams and trees have to be in sync for indices to work properly across them"
        new_teams = [[m for m in t if m.is_alive]for t in self.teams]
        self.teams = new_teams
        self.strtrees = [STRtree([m.posn for m in t])for t in self.teams]
        
def main():
    time_inc = .1 #use 10th seconds
    turn = 0
    game_model = GameModel()
    game_model.setup()
    while not game_model.game_over and turn < 500:
        game_model.game_time += time_inc
        turn +=1
        if turn%10 == 0:
            db(2,f'Turn {turn}:')
        game_model.update(time_inc) 
    db(1,f'Team {game_model.winner} won!' if game_model.winner !=2 else f'It was a tie!')

if __name__ == "__main__":
    main()