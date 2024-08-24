"""
Sprite Collect Rotating Coins

Simple program to show basic sprite usage.

Artwork from https://kenney.nl

If Python and Arcade are installed, this example can be run from the command line with:
python -m arcade.examples.sprite_collect_rotating
"""

import random
import arcade
import os
from pathlib import Path
from enum import Enum

# --- Constants ---
SPRITE_SCALING_PLAYER = 0.5
SPRITE_SCALING_COIN = 0.2
COIN_COUNT = 50

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Sprite Collect Rotating Coins Example"

class Mob(arcade.SpriteList):
    Sprite_part = Enum('Sprite_part',['WEAPON','HANDS','HEAD','BELT','TORSO','LEGS','FEET','BODY','BEHIND'])
    Action = Enum('Action',['bow','hurt','slash','spellcast','thrust','walkcycle'])

    behind = ['quiver']
    belt = ['leather','rope']
    body = ['human','skeleton']
    feet = ['plate_armor_shoes','shoes_brown']
    hands = ['plate_armor_gloves']
    head = ['chain armor_helmet','chain_armor_hood','hair_blonde','leather_armor_hat','plate_armor_helmet','robe_hood']
    legs = ['pants_greenish','plate_armor_pants','robe_skirt']
    torso = ['chain_armor_jacket_purple','chain_armor_torso','leather_armor_bracers',
                'leather_armor_shirt_white','leather_armor_shoulders','leather_armor_torso',
                'plate_armor_arms_shoulders','plate_armor_torso','robe_shirt_brown']
    weapon = ['spear','dagger','staff','bow','arrow','shield_cutout_body','shield_cutout_chain_armor_helmet']

    sprite_wd, sprite_ht = 64,64
    sprite_sheet_dims = { #columns, rows
        Action.bow:(13,4),
        Action.hurt:(6,1),
        Action.slash:(6,4),
        Action.spellcast:(7,4),
        Action.thrust:(8,4),
        Action.walkcycle:(9,4)}
    textures = {}
    
    @classmethod
    def load_mob_textures(cls): #builds nested dicts of textures
        root = Path('.')/ 'textures' / 'png'
        for a in cls.Action:
            sublocns = [[cls.sprite_wd*i,cls.sprite_ht*j,cls.sprite_wd,cls.sprite_ht] 
                        for i in range(cls.sprite_sheet_dims[a][0]) 
                        for j in range(cls.sprite_sheet_dims[a][1])]
            for s in cls.Sprite_part:
                parts = eval(f'cls.{s.name.lower()}')
                for p in parts:
                    f = (f'{s.name}_{p}.png')  
                    q = root / a.name / f
                    if q.exists():
                        fn = q.as_posix()
                        #print(a,b,p,fn)
                        #print(sublocns)
                        cls.textures.setdefault(a,{}).setdefault(s,{}).setdefault(p,arcade.load_textures(fn,sublocns))


    def __init__(self):
        super().__init__()
        self.parts = {s:None for s in Mob.Sprite_part}
        self.parts[Mob.WEAPON] = 'bow',
        self.parts[Mob.HANDS] = 'plate_armor_gloves',
        self.parts[Mob.HEAD] = 'leather_armor_hat',
        self.parts[Mob.BELT] = 'leather',
        self.parts[Mob.TORSO] = 'leather_armor_bracers',
        self.parts[Mob.LEGS] = 'pants_greenish',
        self.parts[Mob.FEET] = 'shoes_brown',
        self.parts[Mob.BODY] = 'human',
        self.parts[Mob.BEHIND] = 'quiver'

        self.action = Mob.Action.walkcycle
        # Track our state
        self.frame = 0
        self.facing = 2 #0 is up; 1 left; 2 down; 3 down
        self.cur_textures = {s:None for s in Mob.Sprite_part}
        self.textures= [(a, dict([(s,Mob.textures[Mob.Action.bow][s][self.parts[s]]) for s in Mob.Sprite_part])) for a in Mob.Action]

        # load textures
        if Mob.textures == {}:
            Mob.load_mob_textures()
        # for a in Mob.action:
        #     for b in Mob.Sprite_part:
                
        #         self.textures.setdefault(a, Mob.textures[a]['BODY'][self.body])
        #         self.textures.setdefault('climbing', Mob.textures['walkcycle']['BODY'][self.body])
        #         self.textures.setdefault('jumping', Mob.textures['walkcycle']['BODY'][self.body])
        #         self.update_texture()
    
    def setup(self):
        for sp in Mob.Sprite_part:
            self.append(arcade.AnimatedTimeBasedSprite())
        
    def advance_frame(self):
        frames_per_sheet = Mob.sprite_sheet_dims[self.action][0]
        next_frame = (self.frame + 1) % frames_per_sheet
        self.frame = next_frame
        return next_frame

    def update_texture(self):
        for s in Mob.Sprite_part:
            self.cur_textures[s] =  self.textures[self.action][self.facing*Mob.frames_per_sheet + self.frame]

    def update_animation(self, delta_time: float = 1 / 60):

            # Figure out if we need to flip face left or right
            if self.change_x < 0 and self.facing == 3:
                self.facing = 1
                self.update_texture()
            elif self.change_x > 0 and self.facing == 1:
                self.facing = 3
                self.update_texture()

            # Climbing animation
            if self.is_on_ladder:
                self.climbing = True
                self.action = 'climbing'
                self.update_texture()
            if not self.is_on_ladder and self.climbing:
                self.climbing = False
                self.action = 'walking'
                self.update_texture()
            if self.climbing and abs(self.change_y) > 1:
                self.advance_frame()
                self.update_texture()
            if self.climbing:
                return

            # Jumping animation
            if self.change_y > 0 and not self.is_on_ladder:
                return
            elif self.change_y < 0 and not self.is_on_ladder:
                self.action = 'jumping'
                self.update_texture()
                return

            # Idle animation
            if self.change_x == 0:
                self.action = 'walking'
                self.update_texture()
                return

            # Walking animation
            self.advance_frame()
            self.update_texture

class Coin(arcade.Sprite):

    def update(self):
        # Rotate the coin.
        # The arcade.Sprite class has an "angle" attribute that controls
        # the sprite rotation. Change this, and the sprite rotates.
        self.angle += self.change_angle


class MyGame(arcade.Window):
    """ Our custom Window Class"""

    def __init__(self):
        """ Initializer """
        # Call the parent class initializer
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

        # Set the working directory (where we expect to find files) to the same
        # directory this .py file is in. You can leave this out of your own
        # code, but it is needed to easily run the examples using "python -m"
        # as mentioned at the top of this program.
        file_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(file_path)

        # Variables that will hold sprite lists
        self.player_list = None
        self.coin_list = None

        # Set up the player info
        self.player_sprite = None
        self.score = 0

        # Don't show the mouse cursor
        self.set_mouse_visible(False)

        arcade.set_background_color(arcade.color.AMAZON)

    def setup(self):
        """ Set up the game and initialize the variables. """

        # Sprite lists
        self.player_list = arcade.SpriteList()
        self.coin_list = arcade.SpriteList()

        # Score
        self.score = 0

        # Set up the player
        # Character image from kenney.nl
        self.player_sprite = arcade.Sprite(":resources:images/animated_characters/female_person/femalePerson_idle.png",
                                           SPRITE_SCALING_PLAYER)
        self.player_sprite.center_x = 50
        self.player_sprite.center_y = 50
        self.player_list.append(self.player_sprite)

        # Create the coins
        for i in range(COIN_COUNT):
            # Create the coin instance
            # Coin image from kenney.nl
            coin = arcade.Sprite(":resources:images/items/coinGold.png", SPRITE_SCALING_COIN)

            # Position the coin
            coin.center_x = random.randrange(SCREEN_WIDTH)
            coin.center_y = random.randrange(SCREEN_HEIGHT)

            # Set up the initial angle, and the "spin"
            coin.angle = random.randrange(360)
            coin.change_angle = random.randrange(-5, 6)

            # Add the coin to the lists
            self.coin_list.append(coin)

    def on_draw(self):
        """ Draw everything """
        self.clear()
        self.coin_list.draw()
        self.player_list.draw()

        # Put the text on the screen.
        output = f"Score: {self.score}"
        arcade.draw_text(output, 10, 20, arcade.color.WHITE, 14)

    def on_mouse_motion(self, x, y, dx, dy):
        """ Handle Mouse Motion """

        # Move the center of the player sprite to match the mouse x, y
        self.player_sprite.center_x = x
        self.player_sprite.center_y = y

    def on_update(self, delta_time):
        """ Movement and game logic """

        # Call update on all sprites (The sprites don't do much in this
        # example though.)
        self.coin_list.update()

        # Generate a list of all sprites that collided with the player.
        hit_list = arcade.check_for_collision_with_list(self.player_sprite, self.coin_list)

        # Loop through each colliding sprite, remove it, and add to the score.
        for coin in hit_list:
            coin.remove_from_sprite_lists()
            self.score += 1


def main():
    """ Main function """
    window = MyGame()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()