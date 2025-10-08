# aPEOSI

## ahfuba's Python Emulated Operating System Interface

A Python based DOS/OS Simulator, made for fun and understanding WHY Python is really unfit for programming operating systems/kernels that require less consumption of system resources, which allows users to execute commands or run applications without the limitation of resources.

It also is a project to understand the fundamentals of the front-end of an OS.

This is a fun project. It needs a computer with an already installed operating system; and also a Python installation.

### Why?

Well, at first I was going to program something similar to "simulator"s you see on Scratch, or a Windows Simulator/Starter you see on Android. Which, is either just a fancy "file explorer", thus not being fit for the name of an OS Simulation; or a simulation made in a game engine with only the graphical elements and some basic functions, again not being fit to be a complete OS simulation in my opinion. 

Therefore, I went and decided to program something sees a `\disks` folder from Windows (or any other OS you are using) file system as Devices/Disks connected to the "virtual" computer. (Well, this isn't a virtual machine, so it's just going to inherit the system information of your own computer) You will be able to change the disk/device type by editing a config file inside the folder.

There is a base kernel that works, not same, but similar to a kernel. The model I was inspired was Windows NT, because it was more of a closed ecosystem than Linux kernel (please don't execute me Arch fans) which was perfect for such a project.

Well, I actually got this "kernel inspiration" idea by asking. I certainly don't know what I am doing or why I am doing this. So... um... yea.

<!--### How does it work?

The way it works is, first and foremost, carcinogenic. Python is a high-level language, making it REALLY heavy and resource-intensive, which makes this simulation WAY slower than a simulator written in C, C++, or any other low- to mid-level language.

When you first run setup.bat, it runs setup.py (duh). This adds an `A` disk (OS disk) and a `BOOT` disk. That’s all it adds. You expected more? Great. Lick your palm.

Then, it basically clones the GitHub repo into this A disk, in a folder called `"apeos"`, and, similar to Windows creating an MBR partition on your disk, it also creates another partition called `"C:"`, and a `"Windows"` folder under the disk `"C:"`, allowing the notation `"C:\Windows"`. With the same logic, a file location in Windows would be: `<folder you put the setup in>\disks\A\newfolder\blabla.bla`, meanwhile in aPEOSI, it would be: `A:/newfolder/blabla.bla`.

When installed correctly using the `setup.bat`, you will be able to run the OS simulation in a windows by running `py/python/pythonX apeosi.py`, running the OS.

In the background; -->

**IMPORTANT:** Any harm done by files or applications run by my app is out of my responsibility. Use the app at your own risk. Execute programs or open files at your own risk.

###### This app is licenced under MIT License.
###### Make sure you give attribution when using/modifying it. You are free to do so.
