# coding:utf-8

from main import main
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from loguru import logger
import os
import matplotlib.pyplot as plt
import random
import shelve
PATH = os.getcwd()
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient
from zipfile import ZipFile
import os
import pandas

if __name__ == '__main__':
    main()
