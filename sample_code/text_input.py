import arcade
import arcade.gui as gui

# --- Method 1 for handling click events,
# Create a child class.
class QuitButton(arcade.gui.UIFlatButton):
    def on_click(self, event: arcade.gui.UIOnClickEvent):
        arcade.exit()

class MyWindow(arcade.Window):
    def __init__(self):
        super().__init__(400, 300, "UI Example", resizable=True)
        self.manager = gui.UIManager()
        self.manager.enable()

        arcade.set_background_color(arcade.color.BEIGE)
        
        # Create a text label
        self.label = arcade.gui.UILabel(
            text="look here for change",
            text_color=arcade.color.DARK_RED,
            width=350,
            height=40,
            font_size=24,
            font_name="Kenney Future")

        # Create an text input field
        self.input_field = gui.UIInputText(
          color=arcade.color.DARK_BLUE_GRAY,
          font_size=24,
          width=200,
          text='Hello ..')

        # Create a button
        submit_button = gui.UIFlatButton(
          color=arcade.color.DARK_BLUE_GRAY,
          text='Submit')
        # --- Method 2 for handling click events,
        # assign self.on_click_start as callback
        submit_button.on_click = self.on_click 
        
        self.v_box = gui.UIBoxLayout()
        self.v_box.add(self.label.with_space_around(bottom=0))
        self.v_box.add(self.input_field)
        self.v_box.add(submit_button)
        self.v_box.add(QuitButton(text="Quit"))
        
        self.manager.add(
            arcade.gui.UIAnchorWidget(
                anchor_x="center_x",
                anchor_y="center_y",
                child=self.v_box)
        )


    def update_text(self):
        print(f"updating the label with input text '{self.input_field.text}'")
        self.label.text = self.input_field.text    

    def on_click(self, event):
        print(f"click-event caught: {event}")
        self.update_text()

        
    def on_draw(self):
        arcade.start_render()
        self.manager.draw()


window = MyWindow()
arcade.run()