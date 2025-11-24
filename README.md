# aPEOSI

## ahfuba's Python Emulated Operating System Interface

A Python based DOS/OS Simulator, made for fun and understanding WHY Python is really unfit for programming operating systems/kernels that require less consumption of system resources, which allows users to execute commands or run applications without the limitation of resources.

It also is a project to understand the fundamentals of the front-end of an OS.

This is a fun project. It needs a computer with an already installed operating system; and also a Python installation.

### Why?

Well, at first I was going to program something similar to "simulator"s you see on Scratch, or a Windows Simulator/Starter you see on Android. Which, is either just a fancy "file explorer", thus not being fit for the name of an OS Simulation; or a simulation made in a game engine with only the graphical elements and some basic functions, again not being fit to be a complete OS simulation in my opinion. 

Therefore I decided to program something from scratch to learn the basics of kernel/OS development, acting as if Windows is the BIOS/Bootloader. (some of my friends called me a masochist)

Afterwards, I went and decided to program something sees a `\disks` folder from Windows (or any other OS you are using) file system as Devices/Disks connected to the "virtual" computer. (Well, this isn't a virtual machine, so it's just going to inherit the system information of your own computer) You will be able to change the disk/device type by editing a config file inside the folder.

There is a base kernel that works, not same, but similar to a kernel. The model I was inspired was Windows NT, because it was more of a closed ecosystem than Linux kernel (please don't execute me Arch fans) which was perfect for such a project.

Well, I actually got this "kernel inspiration" idea by asking. I certainly don't know what I am doing or why I am doing this. So... um... yea.

### How does it work?

The way it works is, first and foremost, carcinogenic. Python is a high-level language, making it REALLY heavy and resource-intensive, which makes this simulation WAY slower than a simulator written in C, C++, or any other low- to mid-level language.

When installed correctly using the `setup.bat`, you will be able to run the OS simulation in a window by running `py/python/pythonX apeosi.py`, running the OS.

##### Tasks, main schedule and OS interface. (As of alpha-1)

The whole aPEOS runs on a task called MAIN. The task manager first schedules the MAIN task and prepares the related task run-lanes, when the app is booted up.  A run-lane means any task related to the current task and their paths and variables are stored beforehand any possible launch choice of the user.

After the MAIN task launches, user basically chooses system tasks or other application tasks that may be launched over the MAIN task itself. MAIN task works in turns with the task manager, which basically, MAIN task works as an interface for the user, and task manager is the backend for it.

**IMPORTANT:** Any harm done by files or applications run by my app is out of my responsibility. Use the app at your own risk. Execute programs or open files at your own risk. The applications I put within the OS interface are ~~hopefully~~ safe, so you can run them pretty much without too many risks. However, if you are running any kind of a modified version of aPEOSI, I strictly reject any form of responsibility, even though the problems are caused from the unedited parts of the code.

###### This app is licenced under MIT License.
###### Make sure you give attribution when using/modifying it. You are free to do so.
