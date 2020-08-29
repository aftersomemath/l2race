# models that take car_command and car_state and produce next car_state.
# these models are local to the client and are used for control in e.g. MPC

from abc import ABC # Abstract Base Class python
import copy

from src.l2race_utils import my_logger
logger = my_logger(__name__)

from src.car import car
from src.car_command import car_command
from src.car_state import car_state

class client_car_model(ABC):
    """
    Abstract base class for client car models
    """
    def __init__(self, car:car=None) -> None:
        self.time=0 # current time of our model
        self.car=car
        pass

    def update_state(self, update_enabled:bool, t:float, car_command:car_command,  real_car:car, modeled_car: car) -> None:
        """
        Take input time, car_state, and car_command and update the car_state.

        :param update_enabled: True to update model, False to clone the car_state.
        :param t: new time in seconds.
        :param car_command: car_command.
        :param real_car: real car with state we are modeling.
        :param modeled_car: ghost modeled car whose car_state to update.
        """
        pass


class linear_extrapolation_model(client_car_model):
    """
    Simple model where the car just keeps going in same direction with constant velocity.
    """

    def __init__(self, car: car = None) -> None:
        super().__init__(car)

    def update_state(self, update_enabled:bool, t: float, car_command: car_command, real_car:car, modeled_car: car) -> None:
        """
        Take input time, car_state, and car_command and update the car_state.

        :param update_enabled: True to update model, False to clone the car_state.
        :param t: new time in seconds.
        :param car_command: car_command.
        :param real_car: real car with state we are modeling.
        :param modeled_car: ghost modeled car whose car_state to update.
        """
        dt=t-self.time
        self.time=t
        if update_enabled:
            if dt<0:
                logger.warning('nonmonotonic timestep of {:.3f}s, setting dt=0'.format(dt))
                return
            modeled_car.car_state.position_m+= dt * modeled_car.car_state.velocity_m_per_sec
            modeled_car.car_state.body_angle_deg+= dt * modeled_car.car_state.yaw_rate_deg_per_sec
        else:
            modeled_car.car_state = copy.copy(real_car.car_state)  # make copy that just copies the fields
            modeled_car.car_state.command=copy.copy(real_car.car_state.command) # and our own command

        # logger.info('\nreal car state:  {}\nghost car state: {}'.format(real_car.car_state,modeled_car.car_state))
