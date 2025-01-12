import os
import site
import cv2
import base64
import numpy as np
from tqdm import tqdm
from datetime import datetime
from stable_baselines3.common.vec_env import VecVideoRecorder, DummyVecEnv
from pathlib import Path
from IPython import display as ipythondisplay
import subprocess
import sys


def run_command(cmd: str, stderr=subprocess.STDOUT) -> None:
    """Run a command in terminal

    Copied from: https://stackoverflow.com/questions/64920923/print-realtime-output-of-subprocess-in-jupyter-notebook

    Args:
        cmd (str): command to run in terminal
        stderr (subprocess, optional): Where the error has to go. Defaults to subprocess.STDOUT.

    Raises:
        e: Excetion of the CalledProcessError
    """
    out = None
    try:
        out = subprocess.check_output(
            [cmd],
            shell=True,
            stderr=stderr,
            universal_newlines=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR {e.returncode}: {cmd}\n\t{e.output}", flush=True, file=sys.stderr)
        raise e
    print(out)


def setup_notebook():
    if "google.colab" in str(get_ipython()):  # noqa:
        print("Running on CoLab.")

        # Required to source ros in new processes
        os.environ["EAGERX_COLAB"] = "1"

        # Reload pil
        import importlib
        import PIL

        importlib.reload(PIL.TiffTags)

        try:
            import eagerx_gui
        except ImportError:
            # Setup virtual display
            command = "echo 'Setting up virtual display for visualisation' && apt-get install ffmpeg freeglut3-dev xvfb >> /tmp/eagerx_xvfb.txt 2>&1"
            run_command(command)
            os.system("Xvfb :1 -screen 0 1024x768x24 &")
            os.environ["DISPLAY"] = ":1"

            # Install eagerx-gui and deps
            command = (
                "echo 'Installing eagerx-gui dependencies' && pip install pyqt5 pyqtgraph >> /tmp/eagerx_gui_deps.txt 2>&1"
            )
            run_command(command)

            command = "echo 'Installing eagerx-gui' && pip install --ignore-requires-python --no-deps eagerx-gui >> /tmp/eagerx_gui.txt 2>&1"
            run_command(command)

            # Install opencv headless
            command = "echo 'Installing opencv-python-headless' && pip uninstall -y opencv-python opencv-python-headless >> /tmp/opencv_uninstall.txt 2>&1 && pip install opencv-python-headless >> /tmp/opencv_uninstall.txt"
            run_command(command)
    else:
        print("Not running on CoLab.")
        try:
            import eagerx_gui
        except ImportError:
            command = "echo 'Installing eagerx-gui' && pip install eagerx-gui >> /tmp/eagerx_gui.txt 2>&1"
            run_command(command)
    os.environ["EAGERX_RELOAD"] = "1"


def deprecated_setup_notebook():
    if "google.colab" in str(get_ipython()):  # noqa:
        print("Running on CoLab.")
        # Required to source ros in new processes
        os.environ["EAGERX_COLAB"] = "1"
        # Set paths to ROS libraries (instead of sourcing)
        site.addsitedir("/opt/ros/melodic/lib/python2.7/dist-packages")
        site.addsitedir("/usr/lib/python2.7/dist-packages")
        os.environ["ROS_PACKAGE_PATH"] = "/opt/ros/melodic/share/"
    else:
        print("Not running on CoLab.")
        print('Execute ROS commands as "!...".')

    os.environ["EAGERX_RELOAD"] = "1"

    try:
        import rospy, roslaunch, rosparam, rospkg  # noqa:

        pkg = rospkg.RosStack()
        if "noetic" in pkg.get_path("ros"):
            ros_version = "noetic"
        elif "melodic" in pkg.get_path("ros"):
            ros_version = "melodic"
        else:
            raise ModuleNotFoundError("No ROS version (noetic, melodic) available. Check if installed & sourced.")
        print(f"ROS {ros_version} available.")
    except ModuleNotFoundError:
        ModuleNotFoundError("No ROS version (noetic, melodic) available. Check if installed & sourced.")

    # No restart possible.
    if "google.colab" in str(get_ipython()):  # noqa:
        timestamp = datetime.today().strftime("%H:%M:%S")
        try:
            roscore.terminate()
            print(f"Roscore restarted: {timestamp}.")
        except NameError:
            print(f"Roscore started: {timestamp}.")

        # Start the roscore node
        roscore = subprocess.Popen(["bash", "/root/roscore"])  # noqa:


def record_video(env, model, video_length=500, prefix="", video_folder="videos/"):
    """
    Adapted from https://colab.research.google.com/github/Stable-Baselines-Team/rl-colab-notebooks/blob/sb3/stable_baselines_getting_started.ipynb

    :param env_id: (str)
    :param model: (RL model)
    :param video_length: (int)
    :param prefix: (str)
    :param video_folder: (str)
    """
    eval_env = DummyVecEnv([lambda: env])

    # Start the video at step=0 and record for video length
    eval_env = VecVideoRecorder(
        eval_env,
        video_folder=video_folder,
        record_video_trigger=lambda step: step == 0,
        video_length=video_length,
        name_prefix=prefix,
    )

    obs = eval_env.reset()
    for _ in range(video_length):
        action, _ = model.predict(obs, deterministic=True)
        obs, _, _, _ = eval_env.step(action)

    # Close the video recorder
    eval_env.close()


def show_video(video_file, video_folder="videos/"):
    """
    Adapted from https://colab.research.google.com/github/Stable-Baselines-Team/rl-colab-notebooks/blob/sb3/stable_baselines_getting_started.ipynb

    which was taken from https://github.com/eleurent/highway-env

    :param video_path: (str) Path to the folder containing videos
    :param prefix: (str) Filter the video, showing only the only starting with this prefix
    """
    html = []
    mp4 = Path(video_folder) / f"{video_file}.mp4"
    video_b64 = base64.b64encode(mp4.read_bytes())
    html.append(
        """<video alt="{}" autoplay 
                loop controls style="height: 400px;">
                <source src="data:video/mp4;base64,{}" type="video/mp4" />
            </video>""".format(
            mp4, video_b64.decode("ascii")
        )
    )
    ipythondisplay.display(ipythondisplay.HTML(data="<br>".join(html)))


def show_svg(svg_file: str, width: str = "100%"):
    """Show SVG image in Jupyter notebook with custom size.

    Adapted from https://stackoverflow.com/questions/51452569/how-to-resize-rescale-a-svg-graphic-in-an-ipython-jupyter-notebook
    (Comment from Jay M)

    :param svg_file: Path or filename.
    :param width: Width of the svg.
    :return: HTML of SVG
    """
    svg_file = svg_file if svg_file.lower().endswith(".svg") else svg_file + ".svg"
    svg = str.encode(ipythondisplay.SVG(svg_file).data)
    b64 = base64.b64encode(svg).decode("utf=8")
    text = f'<img width="{width}" src="data:image/svg+xml;base64,{b64}" >'
    return ipythondisplay.HTML(text)


def evaluate(model, env, n_eval_episodes=3, episode_length=100, video_rate=None, video_prefix=""):
    video_folder = "videos/"
    # Create output folder if needed
    os.makedirs(video_folder, exist_ok=True)

    episodic_rewards = []
    for i in range(n_eval_episodes):
        print(f"Start evaluation episode {i} of {n_eval_episodes}")
        img_array = []
        episodic_reward = 0
        obs = env.reset()
        for _step in tqdm(range(episode_length)):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, info = env.step(action)
            episodic_reward += reward
            if video_rate is not None:
                img = env.render("rgb_array")
                if 0 not in img.shape:
                    img_array.append(img)

        if video_rate is not None:
            video_file = f"{video_prefix}_{i}"
            path = Path(video_folder) / video_file
            print("Start video writer")
            height, width, _ = img_array[-1].shape
            size = (width, height)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(f"{video_folder}/temp.mp4", fourcc, video_rate, size)

            for img in img_array:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                out.write(img)
            out.release()

            os.system(
                f"ffmpeg -y -i {video_folder}/temp.mp4 -vcodec libx264 -f mp4 {path}.mp4 >> /tmp/ffmpeg_{video_prefix}_{i}.txt 2>&1"
            )

            print(f"Showing episode {i} with episodic reward: {episodic_reward}")
            show_video(video_file=video_file, video_folder=video_folder)

            os.remove(f"{video_folder}/temp.mp4")

        episodic_rewards.append(episodic_reward)
    mean_episodic_reward = np.mean(episodic_rewards)
    print(f"Finished evaluation with mean episodic reward: {mean_episodic_reward}")
