# Driver control input from keyboard
from threading import Thread
from typing import Tuple
import pygame

from src.l2race_utils import my_logger
from src.globals import *

from tkinter import *
logger = my_logger(__name__)

from src.car_command import car_command
from src.user_input import user_input

def show_help():
    print(HELP)

    # TODO show help in popup window, not so easy in python...
    thread=Thread(target=show_tk_help)
    thread.start()

def show_tk_help():
    root = Tk()
    root.withdraw()
    var = StringVar()
    label = Message( root, textvariable=var, relief=RAISED)
    var.set(HELP)
    label.pack()
    root.mainloop()


class my_keyboard:

    def __init__(self):
        """
        Makes a new my_keyboard

        :returns: new instance.

        """
        pygame.init()
        self.car_command:car_command = car_command()
        self.user_input:user_input = user_input()
        self.any_key_pressed=False # set true if any key is pressed
        self.auto_pressed=False # only used to log changes to/from autodrive
        self.run_user_model_pressed=False # only used to log changes to/from running user model
        self.restart_pressed=False # only used to log restarts and prevent multiple restarts being sent

    def read(self) -> Tuple[car_command,user_input]:
        pressed = pygame.key.get_pressed()

        self.car_command.throttle = 0.
        self.car_command.brake = 0.
        self.car_command.steering = 0.
        self.user_input.restart_car=False
        self.user_input.restart_client=False
        self.user_input.run_client_model=False
        self.user_input.record_data=False

        self.any_key_pressed=any(pressed)

        if pressed[pygame.K_y]:
            self.car_command.autodrive_enabled = True
            if not self.auto_pressed:
                logger.info('autodriver enabled')
                self.auto_pressed=True
        else:
            self.car_command.autodrive_enabled = False
            if self.auto_pressed:
                logger.info('autodriver disabled')
                self.auto_pressed=False

        if pressed[pygame.K_m]:
            self.user_input.run_client_model = True
            if not self.run_user_model_pressed:
                logger.info('run user model enabled')
                self.run_user_model_pressed=True
        else:
            self.car_command.run_client_model = False
            if self.run_user_model_pressed:
                logger.info('run user model  disabled')
                self.run_user_model_pressed=False

        if pressed[pygame.K_UP] or pressed[pygame.K_w]:
           self.car_command.throttle=1.
           self.car_command.brake=0.
        elif pressed[pygame.K_DOWN] or pressed[pygame.K_s]:
           self.car_command.throttle=0.
           self.car_command.brake=1.
        elif pressed[pygame.K_SPACE]:
            pass
        elif pressed[pygame.K_y]:
            pass

        if pressed[pygame.K_RIGHT] or pressed[pygame.K_d]:
            self.car_command.steering = +1. # steer in negative angle direction, i.e. CW
        elif pressed[pygame.K_LEFT] or pressed[pygame.K_a]:
            self.car_command.steering = -1. # steer in positive angle, i.e. CCW
        else:
            self.car_command.steering = 0.

        if pressed[pygame.K_SPACE]:
            self.car_command.reverse = True
        else:
            self.car_command.reverse = False

        if pressed[pygame.K_ESCAPE]:
            self.user_input.quit = True

        if pressed[pygame.K_r]:
            if not self.restart_pressed: # if it was not pushed before, then set flag true
                if (pygame.key.get_mods() & pygame.KMOD_LSHIFT):
                    self.user_input.restart_client =True
                else:
                    self.user_input.restart_car =True
                self.restart_pressed=True # mark that we set the flag
        else: # if r key not pressed anymore
                self.restart_pressed=False

        if pressed[pygame.K_QUESTION] or pressed[pygame.K_h]:
            show_help()

        return self.car_command, self.user_input



