"""
Platformer Game

python -m arcade.examples.platform_tutorial.11_animate_character
"""
import math
import random
import mobmodel
import importlib
importlib.reload(mobmodel)
from mobmodel import MobModel, MobTypeModel,GameModel
import os
from dataclasses import dataclass
from pathlib import Path

from mobmodel import MobTypeModel, MobModel, GameModel, Action
import arcade
import arcade.gui as gui

MAIN_MENU_VIEW = None
GAME_VIEW = None
GAME_OVER_VIEW = None

class MobTypeView(): #holds assets and stats common to a group of mobs with same art
    """
    The MobType class holds common assets for a group of identical sprites.  
    The Mob (Mobile OBject) class actually causes the instantiation of the MobType.
    """
    registry ={}

    actions_base = [Action.walk, Action.hurt]
    actions_full = actions_base + [Action.slash, Action.spellcast, Action.thrust]

    SPRITE_ROOT = Path('.') / 'textures' / 'png'/ '03_final'

    std_sprite_dims = (64,64)
    ov_sprite_dims = (192,192)

    sprite_sheet_dims = { #row, columns of frames in sprite sheets
        Action.idle:(4,1),
        Action.shoot:(4,13),
        Action.hurt:(1,6),
        Action.slash:(4,6),
        Action.spellcast:(4,7),
        Action.thrust:(4,8),
        Action.walk:(4,9)
    }

    @classmethod
    def setup_all(cls):
        for mt in cls.registry.values():
            mt.setup()

    def __init__(self, name, actions_w_sizes): #name of sprite sheets
        self.name = name
        self.actions_w_sizes = actions_w_sizes 
        self.textures = {}
        self.img_locns = {a:None for a in Action} #list of Rects

        MobTypeView.registry[name] = self
        
    def load_textures(self):
        for a in self.actions_w_sizes.keys():
            a_src = a if a!= Action.idle else Action.walk
            fn = (MobTypeView.SPRITE_ROOT/f'{a_src.name}/{self.name}.png').as_posix()
            #print(fn, a.name, self.img_locns[a][:5])
            self.textures[a] = arcade.load_textures(fn,self.img_locns[a])

    def setup_img_locns(self): #dict action:(list of boxes (4-tuples) for std, list of boxes for ov)
        def build_sheet_img_locns(s_wd,s_ht,rows,cols):
            return [[s_wd*j,s_ht*i,s_wd,s_ht] for i in range(rows) for j in range(cols)] #i is outer loop, j is inner
        
        for a in  Action:
            rows,cols = MobTypeView.sprite_sheet_dims[a]
            std_wd,std_ht = MobTypeView.std_sprite_dims
            ov_wd,ov_ht = MobTypeView.ov_sprite_dims
            if self.actions_w_sizes[a] == 0:
                self.img_locns[a] = build_sheet_img_locns(std_wd,std_ht,rows,cols)
            else:
                self.img_locns[a] = build_sheet_img_locns(ov_wd,ov_ht,rows,cols)

    def setup(self):
        self.setup_img_locns()
        self.load_textures()
        # self.build_animation_key_frames()
        # self.show_keyframes()   
        
class MobView(arcade.Sprite):

    def __init__(self, mob_type_view_name, mob_model:MobModel):#mob_type_name should be for an already registered mob type
        super().__init__()
        self.mob_type_view_name = mob_type_view_name
        self.mob_type_view = None #assigned in setup
        self.mob_model = mob_model   
        # Track our state
        self.last_action = Action.walk
        self.action = Action.walk
        self.frame_idx = 0 #varies between 0 and the len of an actions rows (sprite sheet dims)
        self.facing = 2 #0 is up; 1 left; 2 down; 3 right
        self.time_counter = 0.0
        self.frames = {}
         #only applies to non-looping actions.  'Walk' and pseudo-action 'idle' excluded.

    def setup(self):
        self.mob_type_view = MobTypeView.registry[self.mob_type_view_name]
        self.textures = self.mob_type_view.textures
        self.build_animation_key_frames()
        #self.show_keyframes()
        self.update_texture()

    def update(self):
        mm = self.mob_model
        if type(mm) != MobModel:
            raise ValueError("mob model should be valid when update called.")
        new_x,new_y = GameView.convert_posn(mm.posn.x,mm.posn.y) 
        self.change_x = new_x - self.center_x
        self.change_y = new_y - self.center_y
        self.center_x = new_x
        self.center_y = new_y
        vert_mvt = GameView.ht_wd_ratio < self.change_y/self.change_x if self.change_x != 0 else self.change_y != 0
        fwd_mvt = self.change_y < 0
        bkwd_mvt  = self.change_y > 0
        left_mvt = self.change_x < 0
        right_mvt = self.change_x > 0
        #facing - 0 is up; 1 left; 2 down; 3 right
        if vert_mvt: #facing is up or down
            self.facing = 0 if bkwd_mvt else 2
        else:
            self.facing = 1 if left_mvt else 3 if right_mvt else self.facing
        self.last_action = self.action
        self.action = mm.action

    #key frames have to live in mob views b/c they are model dependent    
    def build_animation_key_frames(self): #build during setup after mob_type_view is asssigned.
        def build_key_frames_per_action(a:Action, cycle_time)->None: #cycle time is in seconds
            facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[a]
            duration = 1000 * cycle_time // (frame_ct )
            self.frames[a] = []
            for facing in range(facing_ct):
                a_src = a if a != Action.idle else Action.walk
                self.frames[a] +=([
                    arcade.AnimationKeyframe(frame_idx,duration,self.textures[a_src][facing*frame_ct + frame_idx]) 
                        for frame_idx in range(frame_ct)]) 
        
        #idle
        build_key_frames_per_action(Action.idle,.5)
        
        # walk
        build_key_frames_per_action(Action.walk, 1.5)

        #hurt
        build_key_frames_per_action(Action.hurt, MobTypeModel.dying_time)

        #attacks
        for a,stats in self.mob_model.atk_stats_dict.items():
            atks_sec = stats.atks_sec
            build_key_frames_per_action(a, atks_sec)     

    def show_keyframes(self): #debugging
        for a,frames in self.frames.items():
            facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[a]
            print(a.name+':')
            facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[a]
            print(f'{facing_ct},{frame_ct},{len(frames)}')
            for facing in range(facing_ct):
                print([frames[facing*frame_ct + frame_idx].duration for frame_idx in range(frame_ct)])
                #print([self.frames[a][facing*frame_ct + frame_idx] for frame_idx in range(frame_ct)])
 
    def update_animation(self, delta_time: float = 1 / 60):
        if self.last_action == self.action:
            self.time_counter += delta_time
        else:
            self.time_counter = 0.0
            self.frame_idx = 0
        facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[self.action]
        #we look at duration for frame in first row, since durations are the same per column
        while self.time_counter > self.frames[self.action][self.frame_idx].duration / 1000.0:
            self.time_counter -= self.frames[self.action][self.frame_idx].duration / 1000.0
            self.frame_idx += 1
            if self.frame_idx >= frame_ct:
                if self.action == Action.hurt:
                    self.frame_idx = frame_ct - 1
                else:
                    self.frame_idx = 0

        self.update_texture()
        # if self.time_counter > self.cur_frame().duration:
        #     self.advance_frame()
        #     self.update_texture()
        #     self.time_counter = 0.0

    # def cur_frame(self):
    #     facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[self.action]
    #     return self.frames[self.action][self.facing*frame_ct+ self.frame_idx]

    def advance_frame(self):
        facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[self.action]
        self.frame_idx = (self.frame_idx + 1) % frame_ct

    def update_texture(self): #assumes facing, frame_idx and action are accurate
        facing_ct,frame_ct = MobTypeView.sprite_sheet_dims[self.action]
        facing = self.facing if facing_ct==4 else 0 #Hurt has only one facing
        if self.mob_type_view is None:
            raise AttributeError("Setup should be called before update_textures.")
        self.texture =  self.textures[self.action][facing*frame_ct + self.frame_idx]

class MainMenu(arcade.View):
    """Class that manages the 'menu' view."""

    def __init__(self):
        super().__init__()
        self.input_dict_valid = False
        self.error_msgs =[]
        self.error_text_area = gui.UITextArea(
                text="",
                width=400,
                align='left',
                text_color=arcade.color.RED,
                font_size=12)

        default_style = {
            "font_name": ("calibri", "arial"),
            "font_size": 15,
            "font_color": arcade.color.WHITE,
            "border_width": 2,
            "border_color": None,
            "bg_color": (21, 19, 21),

            # used if button is pressed
            "bg_color_pressed": arcade.color.WHITE,
            "border_color_pressed": arcade.color.WHITE,  # also used when hovered
            "font_color_pressed": arcade.color.BLACK,
        }
        red_style = {
            "font_name": ("calibri", "arial"),
            "font_size": 15,
            "font_color": arcade.color.WHITE,
            "border_width": 2,
            "border_color": None,
            "bg_color": arcade.color.REDWOOD,

            # used if button is pressed
            "bg_color_pressed": arcade.color.WHITE,
            "border_color_pressed": arcade.color.RED,  # also used when hovered
            "font_color_pressed": arcade.color.RED,
        }

        self.input_dict = {} #stores last updates of input
        self.widget_dict = {} #store widget refs

        # Create a text input widget
        self.manager = gui.UIManager()
        self.manager.enable()

        # Combatant mix
        self.team_names = ["Humans","Monsters"]
        self.arch_names = ["heavy_fighter","fighter","archer","caster"]
        top_box = gui.UIBoxLayout()

        # Build input fields and tracker
        teams_box = gui.UIBoxLayout(vertical=False) 
        self.input_dict['teams'] = {}
        for tn in self.team_names:
            self.widget_dict[tn] = {}
            self.input_dict['teams'][tn] = {}
            v_box = gui.UIBoxLayout()
            team_lbl = gui.UILabel(
                        text=tn,
                        align='left',
                        text_color=arcade.color.GREEN,
                        width=200,
                        height=40,
                        font_size=24)   
            v_box.add(team_lbl)
            for an in self.arch_names:
                arch_lbl = gui.UILabel(
                    text=an+"s: ",
                    align='right',
                    text_color=arcade.color.DARK_BLUE,
                    width=200,
                    height=40,
                    font_size=20
                )
                arch_input = gui.UIInputText(
                    color=arcade.color.DARK_BLUE_GRAY,
                    font_size=20,
                    width=100)
                
                self.widget_dict[tn][an] = arch_input
                self.input_dict['teams'][tn][an] = 0
                h_box = gui.UIBoxLayout(vertical=False)
                h_box.add(arch_lbl)
                h_box.add(arch_input)
                v_box.add(h_box)

            teams_box.add(v_box)
        
        # Level input
        lvl_lbl = gui.UILabel(
                text="Level for all combatants:",
                align='right',
                text_color=arcade.color.BLACK,
                width=300,
                height=40,
                font_size=18)
        lvl_input = input = gui.UIInputText(
                    text = "3",
                    color=arcade.color.DARK_BLUE_GRAY,
                    font_size=18,
                    width=100)
        
        self.widget_dict["level"] = lvl_input
        self.input_dict["level"] = int(lvl_input.text)

        lvl_h_box = gui.UIBoxLayout(vertical=False, space_between=20)
        lvl_h_box.add(lvl_lbl)
        lvl_h_box.add(lvl_input)

        # Submit buttons
        submit_scrn_button = gui.UIFlatButton(
          style = default_style,
          width=400,
          text='Load from Screen')
        # assign self.on_click_start as callback
        submit_scrn_button.on_click = self.transit_to_game_view
        
        submit_json_button = gui.UIFlatButton(
          style=default_style,
          width = 400,
          text='Load from JSON')
        submit_json_button.on_click = self.transit_to_game_view

        self.widget_dict["submit_scrn_btn"] = submit_scrn_button
        self.widget_dict["submit_json_btn"] = submit_json_button
        
        btn_h_box = gui.UIBoxLayout(vertical=False)
        btn_h_box.add(submit_json_button)
        btn_h_box.add(submit_scrn_button)
        
         # Add all to top widget
        top_box.add(teams_box)
        top_box.add(lvl_h_box)
        top_box.add(btn_h_box)
        top_box.add(self.error_text_area)
        
        # Anchor and register top widget
        self.manager.add(
            arcade.gui.UIAnchorWidget(
                anchor_x="center_x",
                anchor_y="center_y",
                #child=self.v_box)
                child = top_box)
        )
        
    def on_show_view(self):
        """Called when switching to this view."""
        arcade.set_background_color(arcade.color.WHITE)
        if self.input_dict_valid:
            self.update_widget_dict()

    def on_draw(self):
        """Draw the menu"""
        self.clear()
        self.manager.draw()

    def update_input_dict(self):
        for tn in self.team_names:
            arch_widget_dict = self.widget_dict[tn]
            arch_input_dict = self.input_dict['teams'][tn]
            for an in self.arch_names:
                arch_input_dict[an] = self._handle_int_input(f'{tn}:{an}',arch_widget_dict[an],0,5,0)

        self.input_dict["level"] = self._handle_int_input("level",self.widget_dict["level"],1,50,3)

    def update_widget_dict(self): #called when input_dict is authoritative
        for tn in self.team_names:
            arch_widget_dict = self.widget_dict[tn]
            arch_input_dict = self.input_dict['teams'][tn]
            for an in self.arch_names:
                arch_widget_dict[an].text = str(arch_input_dict[an])

        self.widget_dict["level"].text = str(self.input_dict["level"])

    def _handle_int_input(self, 
                          widget_name:str, 
                          widget:object,
                          min_val:int, 
                          max_val:int, 
                          default_val:int):
        """turns value errors into error messages. Always returns an int value."""
        val_text = widget.text
        val = default_val
        if val_text == "":
            val = default_val
        else:
            try:
                val = int(val_text)
                if (val<min_val or val>max_val):
                    raise ValueError("foo")
                self.input_dict["level"] = val
            except ValueError:
                self.error_msgs.append(f'Input for {widget_name} must be an integer between {min_val} and {max_val}, inclusive.')
                return default_val
        return val

    def transit_to_game_view(self, event): 
        if event is None:
            raise ValueError("event should not be null in setup_gameview")
        if event.source == self.widget_dict["submit_json_btn"]:
            input_data = None
        else:
            self.update_input_dict()
            for tn in self.team_names:
                arch_dict = self.input_dict['teams'][tn]
                result = sum([v for v in arch_dict.values()])
                if result == 0:
                    self.error_msgs.append(f"The count of at least one combatant for team {tn} must be greater than zero.")

            msg = "\n".join(self.error_msgs)
            self.error_text_area.text = msg
            #self.error_text_area.fit_content()
            if len(self.error_msgs) >  0:
                self.error_msgs = []
                return
            else:
                self.input_dict_valid = True
                input_data = self.input_dict

        GAME_VIEW.setup(input_data)
        self.window.show_view(GAME_VIEW)
        
class GameView(arcade.View):
    """
    Main application class.
    """
    # Model / View related
    ht_wd_ratio = 3.0/4.0
    wd_pixels_meter = 32
    ht_pixels_meter = 24

    @classmethod
    def convert_posn(cls,x,y)->tuple:
        return (x * cls.wd_pixels_meter,y*cls.ht_pixels_meter)

    def __init__(self):
        """ 
        Initializer for the game.  Does heavy lifting, so that setup can be fast. 
        Init is called once. Setup is called per combat. 
        """  
        super().__init__()

        self.game_model = GameModel()

        self.mob_layer_name = "Mobs"

        self.fx_list = arcade.ShapeElementList

        # Set the path to start with this program
        file_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(file_path)

        # Our Scene Object
        self.scene = None

        # A Camera that can be used for scrolling the screen
        self.camera = None

        # A Camera that can be used to draw GUI elements
        self.gui_camera = None

        self.end_of_map = 0

        # Keep track of the score
        self.score = 0

        # Load sounds
        self.collect_coin_sound = arcade.load_sound(":resources:sounds/coin1.wav")
        self.jump_sound = arcade.load_sound(":resources:sounds/jump1.wav")
        self.game_over = arcade.load_sound(":resources:sounds/gameover1.wav")
        self.shoot_sound = arcade.load_sound(":resources:sounds/hurt5.wav")
        self.hit_sound = arcade.load_sound(":resources:sounds/hit5.wav")

        # Load MobTypeViews... all are available by default, might change later
        def get_action_w_sizes(is_slash_ov,is_thrust_ov):
            action_w_sizes = { 
                Action.idle:0,
                Action.hurt:0,
                Action.shoot:0,
                Action.slash:is_slash_ov,
                Action.spellcast:0,
                Action.thrust:is_thrust_ov,
                Action.walk:0
            }
            return action_w_sizes
            
        #human team
        MobTypeView('human_heavy_armor_spear_sword',get_action_w_sizes(0,0))
        MobTypeView('human_light_armor_long_sword',get_action_w_sizes(1,1))
        MobTypeView('human_unarmored_bow',get_action_w_sizes(1,0)) 
        MobTypeView('human_spellcaster',get_action_w_sizes(0,1))
        #monster team
        MobTypeView('goblin_heavy_armor_spear_sword',get_action_w_sizes(1,1))
        MobTypeView('wolf_light_armor_long_sword',get_action_w_sizes(1,1))
        MobTypeView('skeleton_light_armor_long_sword',get_action_w_sizes(1,1))
        MobTypeView('lizard_spellcaster',get_action_w_sizes(0,1))
        MobTypeView('troll_heavy_armor_spear',get_action_w_sizes(0,0))
        MobTypeView('skeleton_light_armor_long_sword',get_action_w_sizes(1,1))

        MobTypeView.setup_all()

    def setup(self,input_dict = None):
        """Set up the game here. Call this function to restart the game."""
        # Set up the Game Model, with screen data, if it exists, or config file
        self.game_model.setup(input_dict)

        # Set up the Cameras
        self.camera = arcade.Camera(self.window.width, self.window.height)
        self.gui_camera = arcade.Camera(self.window.width, self.window.height)

        self.scene = arcade.Scene() 

        for i,t in enumerate(self.game_model.teams):
            for m in t:
                archetype = m.mobTypeModel.name
                if i == 0:
                    match archetype:
                        case "heavy_fighter":
                            mvt_name = 'human_heavy_armor_spear_sword'
                        case "fighter":
                            mvt_name = 'human_light_armor_long_sword'
                        case "archer":
                            mvt_name = 'human_unarmored_bow'
                        case "caster":
                            mvt_name = 'human_spellcaster'
                        case _ :
                            raise ValueError("archetype list not complete")
                else:
                    match archetype:
                        case "heavy_fighter":
                            mvt_name = 'goblin_heavy_armor_spear_sword'
                        case "fighter":
                            mvt_name = 'wolf_light_armor_long_sword'
                        case "archer":
                            mvt_name = 'skeleton_light_armor_long_sword'
                        case "caster":
                            mvt_name = 'lizard_spellcaster'            
                        case _ :
                            raise ValueError("archetype list not complete")
                mv = MobView(mvt_name,m)
                self.scene.add_sprite(self.mob_layer_name, mv)
                mv.setup()
            

        # Keep track of the score
        self.score = 0


        # # Add bullet spritelist to Scene
        #self.scene.add_sprite_list(LAYER_NAME_BULLETS)

        # --- Other stuff
        # Set the background color
        #if self.tile_map.background_color:
        #    arcade.set_background_color(self.tile_map.background_color)

    def on_show_view(self):
        arcade.set_background_color(arcade.color.TEA_GREEN)
        # self.setup(MAIN_MENU_VIEW.input_dict)

    def on_draw(self):
        """Render the screen."""

        # Clear the screen to the background color
        self.clear()

        # Activate the game camera
        self.camera.use()

        # Sort mobs by y
        mob_list = self.scene.get_sprite_list(self.mob_layer_name)
        mob_list.sort(key=lambda x: x.position[1], reverse=True)

        # Draw our Scene
        self.scene.draw()

        # Activate the GUI camera before drawing GUI elements
        self.gui_camera.use()

        #update bullets and hits and spells
        for s,t,c in self.game_model.shooting:
            s_p = GameView.convert_posn(s.posn.x,s.posn.y)
            t_p = GameView.convert_posn(t.posn.x,t.posn.y)
            #s_t_v = result = tuple(map(lambda i, j: i - j, t_p, s_p))
            m_coords = arcade.lerp_vec(s_p,t_p, (3-c)/3) + arcade.lerp_vec(s_p,t_p, (4-c)/3)
            
            arcade.draw_line(*m_coords, arcade.color.BABY_BLUE, 3)
            
        for t,c in self.game_model.being_hit:
            t_x,t_y = GameView.convert_posn(t.posn.x,t.posn.y)
            arcade.draw_circle_filled(t_x, t_y, 15, arcade.csscolor.DARK_RED)
            
        for g,c in self.game_model.spell_geoms:
            if g is not None:
                points = list(g.boundary.coords)
                points = [self.convert_posn(x,y) for x,y in points]
                arcade.draw_polygon_filled(points, tuple(arcade.color.SPANISH_VIOLET)+(80,))

        # Draw our score on the screen, scrolling it with the viewport
        score_text = f"Score: {arcade.get_fps()}"#{self.score}"
        arcade.draw_text(
            score_text,
            10,
            10,
            arcade.csscolor.BLACK,
            18,
        )

    def center_camera_to_player(self, speed=0.2):
        screen_center_x = self.camera.scale * (self.player_sprite.center_x - (self.camera.viewport_width / 2))
        screen_center_y = self.camera.scale * (self.player_sprite.center_y - (self.camera.viewport_height / 2))
        if screen_center_x < 0:
            screen_center_x = 0
        if screen_center_y < 0:
            screen_center_y = 0
        player_centered = (screen_center_x, screen_center_y)    

        self.camera.move_to(player_centered, speed)

    def on_update(self, delta_time):
        if self.game_model.game_over:
            self.window.show_view(GAME_OVER_VIEW)
            return
        
        """Model and animation updates"""
        #Update game model. This sets all all state that update_animation needs
        self.game_model.update(delta_time)

        # Update Animations
        self.scene.update_animation(
            delta_time,
            [
                self.mob_layer_name,
            ],
        )
        
        # Update moving platforms, enemies, and bullets
        self.scene.update([])

class GameOverView(arcade.View):
    """Class to manage the game overview"""

    def on_show_view(self):
        """Called when switching to this view"""
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        """Draw the game overview"""
        self.clear()
        arcade.draw_text(
            "Game Over - Click to restart",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2,
            arcade.color.WHITE,
            30,
            anchor_x="center",
        )

    def on_mouse_press(self, _x, _y, _button, _modifiers):
        """Use a mouse press to advance to the 'game' view."""
        self.window.show_view(MAIN_MENU_VIEW)

# Screen size
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 1200
SCREEN_TITLE = "Balancer"


def main():
    """Main function"""
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    global MAIN_MENU_VIEW
    MAIN_MENU_VIEW = MainMenu()
    global GAME_VIEW 
    GAME_VIEW = GameView()
    global GAME_OVER_VIEW
    GAME_OVER_VIEW = GameOverView()
    window.show_view(MAIN_MENU_VIEW)
    arcade.run()

if __name__ == "__main__":
    main()