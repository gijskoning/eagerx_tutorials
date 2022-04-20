from typing import List, Optional

# ROS IMPORTS
from std_msgs.msg import Float32MultiArray
from sensor_msgs.msg import Image
from math import pi

# EAGERx IMPORTS
from eagerx_ode.bridge import OdeBridge
from eagerx import Object, EngineNode, SpaceConverter, EngineState
from eagerx.core.specs import ObjectSpec
from eagerx.core.graph_engine import EngineGraph
import eagerx.core.register as register


class Pendulum(Object):
    entity_id = "Pendulum"

    @staticmethod
    @register.sensors(angle_sensor=Float32MultiArray, image=Image)
    @register.actuators(voltage=Float32MultiArray)
    @register.engine_states(model_state=Float32MultiArray)
    @register.config(render_shape=[480, 480])
    def agnostic(spec: ObjectSpec, rate: float):
        """Agnostic definition of the Pendulum.

        Sensors
        angle_sensor: angle data [angle, angular velocity]
        image: render of pendulum system

        Actuators
        voltage: DC motor voltage

        States
        model_state: allows resetting the angle and angular velocity

        Config
        render_shape: shape of render window [height, width]
        """
        # Register standard converters, space_converters, and processors
        import eagerx.converters  # noqa # pylint: disable=unused-import

        # Set observation properties: (space_converters, rate, etc...)
        spec.sensors.angle_sensor.rate = rate
        spec.sensors.angle_sensor.space_converter = SpaceConverter.make(
            "Space_Float32MultiArray", low=[-9999, -9999], high=[9999, 9999], dtype="float32"
        )

        spec.sensors.image.rate = 15
        spec.sensors.image.space_converter = SpaceConverter.make(
            "Space_Image", low=0, high=255, shape=spec.config.render_shape, dtype="uint8"
        )

        # Set actuator properties: (space_converters, rate, etc...)
        spec.actuators.voltage.rate = rate
        spec.actuators.voltage.window = 1
        spec.actuators.voltage.space_converter = SpaceConverter.make(
            "Space_Float32MultiArray", low=[-3], high=[3], dtype="float32"
        )

        # Set model_state properties: (space_converters)
        spec.states.model_state.space_converter = SpaceConverter.make(
            "Space_Float32MultiArray", low=[-pi, -9], high=[pi, 9], dtype="float32"
        )

    @staticmethod
    @register.spec(entity_id, Object)
    def spec(
            spec: ObjectSpec,
            name: str,
            actuators: List[str] = None,
            sensors: List[str] = None,
            states: List[str] = None,
            rate: float = 30.,
            render_shape: List[int] = None,
    ):
        """Object spec of Pendulum"""
        # Performs all the steps to fill-in the params with registered info about all functions.
        Pendulum.initialize_spec(spec)

        # Modify default agnostic params
        # Only allow changes to the agnostic params (rates, windows, (space)converters, etc...
        spec.config.name = name
        spec.config.sensors = sensors if sensors else ["angle_sensor"]
        spec.config.actuators = actuators if actuators else ["voltage"]
        spec.config.states = states if states else ["model_state"]

        # Add custom agnostic params
        spec.config.render_shape = render_shape if render_shape else [480, 480]

        # Add bridge implementation
        Pendulum.agnostic(spec, rate)

    @staticmethod
    @register.bridge(entity_id, OdeBridge)  # This decorator pre-initializes bridge implementation with default object_params
    def ode_bridge(spec: ObjectSpec, graph: EngineGraph):
        """Engine-specific implementation (OdeBridge) of the object."""
        # Import any object specific entities for this bridge
        import eagerx_tutorials.pendulum  # noqa # pylint: disable=unused-import

        # Set object arguments (nothing to set here in this case)
        spec.OdeBridge.ode = "eagerx_tutorials.pendulum.pendulum_ode/pendulum_ode"
        # Set default params of pendulum ode [J, m, l, b, K, R].
        spec.OdeBridge.ode_params = [0.000189238, 0.0563641, 0.0437891, 0.000142205, 0.0502769, 9.83536]

        # Create engine_states (no agnostic states defined in this case)
        spec.OdeBridge.states.model_state = EngineState.make("OdeEngineState")

        # Create sensor engine nodes
        obs = EngineNode.make("OdeOutput", "angle_sensor", rate=spec.sensors.angle_sensor.rate, process=2)
        image = EngineNode.make(
            "OdeRender",
            "image",
            render_fn="eagerx_tutorials.pendulum.pendulum_render/pendulum_render_fn",
            rate=spec.sensors.image.rate,
            process=2,
        )

        # Create actuator engine nodes
        action = EngineNode.make(
            "OdeInput", "pendulum_actuator", rate=spec.actuators.voltage.rate, process=2, default_action=[0]
        )

        # Connect all engine nodes
        graph.add([obs, image, action])
        graph.connect(source=obs.outputs.observation, sensor="angle_sensor")
        graph.connect(source=obs.outputs.observation, target=image.inputs.observation)
        graph.connect(source=action.outputs.action_applied, target=image.inputs.action_applied, skip=True)
        graph.connect(source=image.outputs.image, sensor="image")
        graph.connect(actuator="voltage", target=action.inputs.action)

        # Check graph validity (commented out)
        # graph.is_valid(plot=True)
