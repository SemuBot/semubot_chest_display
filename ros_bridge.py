"""ROS 2 side of the chest display: the topics it uses and the node that talks on them.

The README's "ROS 2 topics" table lists the node at the other end of each topic.
"""

import collections
import json
import threading
import time

FACE_COLOR_TOPIC = "/face/background_color"
SPEECH_MODE_TOPIC = "/semubot/mode"
SPEECH_MODE_STATE_TOPIC = "/semubot/mode_state"
AUDIO_LEVEL_TOPIC = "/semubot/audio_level"  # [rms, speech probability], 10 times per second
VAD_THRESHOLD_TOPIC = "/semubot/vad_threshold"
VAD_THRESHOLD_STATE_TOPIC = "/semubot/vad_threshold_state"
TTS_SETTINGS_TOPIC = "/semubot/tts_settings"  # JSON {"speaker": ..., "speed": ...}
TTS_SETTINGS_STATE_TOPIC = "/semubot/tts_settings_state"  # same plus "speakers"
CONVERSATION_LOG_TOPIC = "/semubot/conversation_log"  # JSON list, latched, memory only
CONVERSATION_LOG_CLEAR_TOPIC = "/semubot/conversation_log_clear"
CLOUD_USAGE_TOPIC = "/semubot/cloud_usage"  # JSON {"today": {...}, "month": {...}, ...}
ROBOT_STATE_TOPIC = "/semubot/state"  # JSON {"stage", "mode", "since"}, latched
SPEED_SCALE_TOPIC = "/semubot/speed_scale"  # Float32 0.1-1.0, latched, multiplies /cmd_vel on the Pi
SPEECH_INPUT_TOPIC = "/speech_input"  # text the robot says out loud
ROS_RETRY_SECONDS = 5  # How often to retry connecting to ROS 2 after a failure


class RobotRos:
    """Keep the chest display's ROS node alive: face color and speech mode topics.

    `face_color` and `speed_scale` return the saved settings, sent again on every (re)connect.
    """

    def __init__(self, face_color, speed_scale):
        self.face_color = face_color
        self.speed_scale = speed_scale
        self.node = None
        self.executor = None
        self.error = None
        self.mode_error = None
        self.speech_mode = None  # Last mode reported by the robot's brain node
        self.vad_threshold = None  # Loudness threshold reported by the brain node
        self.levels = collections.deque(maxlen=200)  # (time, rms, speech probability)
        self.tts_settings = None  # {"speaker", "speed", "speakers"} reported by the brain node
        self.conversation_log = None  # Raw JSON text of the brain node's conversation log
        self.cloud_usage = None  # {"today": {...}, "month": {...}, "model", "priced"}
        self.robot_state = None  # {"stage", "mode", "since"} reported by the brain node
        self.closed = False
        self._connect()
        if self.node is None:
            # ROS can fail at login if the network (CycloneDDS interface) is not up yet: retry.
            threading.Thread(target=self._retry_connect, daemon=True).start()

    def _retry_connect(self):
        while self.node is None and not self.closed:
            time.sleep(ROS_RETRY_SECONDS)
            if not self.closed:
                self._connect()

    def _connect(self):
        node = None
        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
            from rclpy.signals import SignalHandlerOptions
            from std_msgs.msg import Empty, Float32, Float32MultiArray, String

            # The Tk app handles SIGINT/SIGTERM itself (see start_gui).
            rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
            self.rclpy = rclpy
            self.message_type = String
            node = rclpy.create_node("chest_display")
            qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
            self.publisher = node.create_publisher(String, FACE_COLOR_TOPIC, qos)
            self.speed_publisher = node.create_publisher(Float32, SPEED_SCALE_TOPIC, qos)
            self.mode_publisher = node.create_publisher(String, SPEECH_MODE_TOPIC, 10)
            node.create_subscription(String, SPEECH_MODE_STATE_TOPIC, self._speech_mode_state, qos)
            self.float_type = Float32
            self.threshold_publisher = node.create_publisher(Float32, VAD_THRESHOLD_TOPIC, 10)
            node.create_subscription(Float32, VAD_THRESHOLD_STATE_TOPIC, self._threshold_state, qos)
            node.create_subscription(Float32MultiArray, AUDIO_LEVEL_TOPIC, self._audio_level, 10)
            self.tts_publisher = node.create_publisher(String, TTS_SETTINGS_TOPIC, 10)
            self.speech_publisher = node.create_publisher(String, SPEECH_INPUT_TOPIC, 10)
            node.create_subscription(String, TTS_SETTINGS_STATE_TOPIC, self._tts_settings_state, qos)
            self.empty_type = Empty
            self.log_clear_publisher = node.create_publisher(Empty, CONVERSATION_LOG_CLEAR_TOPIC, 10)
            node.create_subscription(String, CONVERSATION_LOG_TOPIC, self._conversation_log, qos)
            node.create_subscription(String, CLOUD_USAGE_TOPIC, self._cloud_usage, qos)
            node.create_subscription(String, ROBOT_STATE_TOPIC, self._robot_state, qos)
            self.executor = SingleThreadedExecutor()
            self.executor.add_node(node)
            self.spin_thread = threading.Thread(target=self._spin, daemon=True)
            self.spin_thread.start()
            self.node = node  # Only now: the screens treat a node as "ROS ready"
            self.error = None
            self.publish(self.face_color())
            self.publish_speed_scale(self.speed_scale())
        except Exception as error:
            self.error = f"{error} (proovin {ROS_RETRY_SECONDS} s pärast uuesti)"
            if self.executor is not None:
                self.executor.shutdown()
                self.executor = None
            if node is not None:
                node.destroy_node()
            self.node = None
            if hasattr(self, "rclpy") and self.rclpy.ok():
                self.rclpy.shutdown()

    def _spin(self):
        try:
            self.executor.spin()
        except Exception:
            pass  # The executor stops when the display closes.

    def _speech_mode_state(self, message):
        self.speech_mode = message.data

    def _threshold_state(self, message):
        self.vad_threshold = message.data

    def _audio_level(self, message):
        if len(message.data) >= 2:
            self.levels.append((time.monotonic(), message.data[0], message.data[1]))

    def _tts_settings_state(self, message):
        try:
            settings = json.loads(message.data)
        except ValueError:
            return
        if isinstance(settings, dict):
            self.tts_settings = settings

    def _conversation_log(self, message):
        self.conversation_log = message.data

    def _cloud_usage(self, message):
        try:
            usage = json.loads(message.data)
        except ValueError:
            return
        if isinstance(usage, dict):
            self.cloud_usage = usage

    def _robot_state(self, message):
        try:
            state = json.loads(message.data)
        except ValueError:
            return
        if isinstance(state, dict):
            self.robot_state = state

    def clear_conversation_log(self):
        if self.node is None:
            return False
        try:
            self.log_clear_publisher.publish(self.empty_type())
            return True
        except Exception as error:
            self.mode_error = str(error)
            return False

    def _publish_string(self, publisher, text):
        if self.node is None:
            return False
        try:
            publisher.publish(self.message_type(data=text))
            self.mode_error = None
            return True
        except Exception as error:
            self.mode_error = str(error)
            return False

    def publish_tts_settings(self, **settings):
        return self._publish_string(self.tts_publisher, json.dumps(settings))

    def say(self, text):
        return self._publish_string(self.speech_publisher, text)

    def recent_levels(self, seconds):
        since = time.monotonic() - seconds
        return [(rms, prob) for stamp, rms, prob in list(self.levels) if stamp >= since]

    def publish_vad_threshold(self, threshold):
        if self.node is None:
            return False
        try:
            self.threshold_publisher.publish(self.float_type(data=float(threshold)))
            self.mode_error = None
            return True
        except Exception as error:
            self.mode_error = str(error)
            return False

    def publish_speed_scale(self, scale):
        if self.node is None:
            return False
        try:
            self.speed_publisher.publish(self.float_type(data=float(scale)))
            self.error = None
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def publish(self, color):
        if self.node is None:
            return False
        try:
            self.publisher.publish(self.message_type(data=color))
            self.error = None
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def publish_speech_mode(self, mode):
        if self.node is None:
            return False
        try:
            self.mode_publisher.publish(self.message_type(data=mode))
            self.mode_error = None
            return True
        except Exception as error:
            self.mode_error = str(error)
            return False

    def close(self):
        self.closed = True
        if self.node is not None:
            self.executor.shutdown()
            self.spin_thread.join(timeout=2)
            self.node.destroy_node()
            self.rclpy.shutdown()
