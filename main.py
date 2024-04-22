# -*- coding: UTF-8 -*-
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, font, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from loguru import logger
import os
import serial
import matplotlib.pyplot as plt
import numpy as np
import random
import shelve
import zipfile
from matplotlib.dates import DateFormatter
from matplotlib.ticker import FuncFormatter
import shutil

PATH = os.getcwd()
import pandas as pd


class control:
    def __init__(self):
        pass

    # def btn_relief_valve_click(self):
    #     self.btn_relief_valve.config(relief="sunken")


class Widgets(tk.Tk):
    """
    1. 该类继承了tk.Tk类，因此可以直接使用Tk类的方法
    """

    def __init__(self):
        tk.Tk.__init__(self)
        self.btn_is_open = [False, False, False, False]
        self.ax = None
        self.fig = None
        self.strvTime = None
        self.thread = None
        self.process_data = []
        self.title("串口调试助手")
        self.geometry("1500x800")
        self.resizable(False, False)
        self.open_time = time.localtime()
        self.data_queue = queue.Queue()
        tk.Tk.protocol(self, 'WM_DELETE_WINDOW', self.quit)
        self.is_open = False
        self._dev_frame = tk.Frame(self)
        self._dev_frame.grid(row=0, column=0, padx=1, pady=1, sticky=tk.NW)
        self.font_1 = font.Font(family="bold", size=30)
        self.font_2 = font.Font(family="bold", size=30)
        self.device_frame_start()
        self.copyright_frame_start()
        self.number_frame_start()
        self.graph_frame_start()
        self.data_frame_start()
        self.btn_frame_start()
        self.mPress = False
        self.start_x = 0
        self.start_y = 0
        self.fig, self.ax = plt.subplots(figsize=(15, 4), dpi=80)  # 创建一个图形和一个坐标轴

        self.ax.grid(True)  # 显示网格
        self.fig.canvas.mpl_connect('scroll_event', self.call_scroll)  # 绑定鼠标滚轮事件
        self.fig.canvas.mpl_connect('button_press_event', self.call_move)  # 绑定鼠标按下事件
        self.fig.canvas.mpl_connect('button_release_event', self.call_move)  # 绑定鼠标松开事件
        self.fig.canvas.mpl_connect('motion_notify_event', self.call_move)  # 绑定鼠标移动事件

        self.x = []  # x轴数据
        self.y = []
        self.line, = self.ax.plot(self.x, self.y)
        self.ax.set_title('Pressure vs Time')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Pressure (Pa)')
        # 将图形添加到tkinter窗口
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.gbGraph)  # A tk.DrawingArea.
        self.canvas.draw()  # 显示图形
        self.ax.fill_between(self.x, self.y, 100, color='white')
        self.ax.set_xlim(0, 150)
        self.ax.set_ylim(0, 10)

        self.canvas.get_tk_widget().grid(row=1, column=1, sticky=tk.NW)  # 显示位置

    def device_frame_start(self):
        """
        设备选择框架
        """
        # Device Choose Frame
        self.gbDevConnect = tk.LabelFrame(self._dev_frame, height=100, width=200, text="设备选择")
        self.gbDevConnect.grid_propagate(True)
        self.gbDevConnect.grid(row=0, column=0, padx=2, sticky=tk.NW)
        # Device Information Frame
        tk.Label(self.gbDevConnect, text="串口号:", font=self.font_1).grid(row=0, column=0, sticky=tk.NW)
        self.cmbDevType = ttk.Combobox(self.gbDevConnect, width=5, font=self.font_1, state="readonly")
        self.cmbDevType.grid(row=0, column=1, sticky=tk.NW)
        self.cmbDevType["value"] = ["com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "com10"]
        self.cmbDevType.current(0)
        self.strvDevCtrl = tk.StringVar()
        self.strvDevCtrl.set("开始记录")
        self.btnDevCtrl = tk.Button(self.gbDevConnect, width=7, font=self.font_1,
                                    textvariable=self.strvDevCtrl, command=self.btn_open_click)
        self.btnDevCtrl.grid(row=2, column=0, sticky=tk.E)

    def copyright_frame_start(self):
        """
        版权信息框架
        """
        # CopyRight Frame
        self.gbDevCopyRight = tk.LabelFrame(self._dev_frame, height=100, width=200, text="版权信息")
        self.gbDevCopyRight.grid_propagate(True)
        self.gbDevCopyRight.grid(row=1, column=0, padx=2, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Author: Liu Bingqian").grid(row=2, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Email: lbq08@foxmail.com").grid(row=3, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Version: 1.0.6").grid(row=4, column=0, sticky=tk.NW)
        # Time Label
        self.strvTime = tk.StringVar()
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, textvariable=self.strvTime).grid(row=5, column=0, sticky=tk.NW)
        self.gettime()

    def data_frame_start(self):
        self.gbData = tk.LabelFrame(self._dev_frame, text="实时值")
        self.gbData.grid_propagate(True)
        self.gbData.grid(row=2, column=0, sticky=tk.NW)
        self.IntVarpressure = tk.IntVar()
        self.IntVarpressure.set(0)
        tk.Label(self.gbData, anchor=tk.NW, text="压力值:", font=self.font_1).grid(row=0, column=0, sticky=tk.NW)
        tk.Label(self.gbData, anchor=tk.NW, textvariable=self.IntVarpressure, font=self.font_1).grid(row=0, column=1,
                                                                                                     sticky=tk.NW)
        # self.IntVartemp = tk.IntVar()
        # self.IntVartemp.set(0)
        # tk.Label(self.gbData, anchor=tk.NW, text="温度值:", font=self.font_1).grid(row=1, column=0, sticky=tk.NW)
        # tk.Label(self.gbData, anchor=tk.NW, textvariable=self.IntVartemp, font=self.font_1).grid(row=1, column=1,
        #                                                                                          sticky=tk.NW)

    def btn_frame_start(self):
        self.gbBtn = tk.LabelFrame(self._dev_frame, height=100, width=200, text="按钮")
        # self.gbBtn.grid_propagate(True)
        # self.gbBtn.grid(row=0, column=2, sticky=tk.NW)

        tk.Label(self.gbBtn, anchor=tk.NW, text="泄压阀控制", font=self.font_1).grid(row=0, column=0, sticky=tk.NW)
        tk.Label(self.gbBtn, anchor=tk.NW, text="高压泵控制", font=self.font_1).grid(row=1, column=0, sticky=tk.NW)
        tk.Label(self.gbBtn, anchor=tk.NW, text="高压进水控制", font=self.font_1).grid(row=2, column=0, sticky=tk.NW)
        self.strvReliefValveCtrl = tk.StringVar()
        self.strvReliefValveCtrl.set("打开")
        self.btnReliefValveCtrl = tk.Button(self.gbBtn, textvariable=self.strvReliefValveCtrl, font=self.font_1,
                                            command=self.btn_1_click, bg="green")
        self.btnReliefValveCtrl.grid(row=0, column=1, sticky=tk.E)
        self.strvHighPressureCtrl = tk.StringVar()
        self.strvHighPressureCtrl.set("打开")
        self.btnHighPressureCtrl = tk.Button(self.gbBtn, textvariable=self.strvHighPressureCtrl, font=self.font_1,
                                             command=self.btn_2_click, bg="green")
        self.btnHighPressureCtrl.grid(row=1, column=1, sticky=tk.E)
        self.strvPressureWaterCtrl = tk.StringVar()
        self.strvPressureWaterCtrl.set("打开")
        self.btnPressureWaterCtrl = tk.Button(self.gbBtn, textvariable=self.strvPressureWaterCtrl, font=self.font_1,
                                              command=self.btn_3_click, bg="green")
        self.btnPressureWaterCtrl.grid(row=2, column=1, sticky=tk.E)

    def number_frame_start(self):
        self.gbNumber = tk.LabelFrame(self._dev_frame, height=100, width=200, text="编号输入")
        self.gbNumber.grid_propagate(True)
        self.gbNumber.grid(row=0, column=1, sticky=tk.NW)
        # columnspan=2, rowspan=2,
        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号:", font=self.font_1).grid(row=0, column=0, sticky=tk.W)
        self.Tank_ID = tk.Entry(self.gbNumber, width=10, font=self.font_1)
        self.Tank_ID.grid(row=0, column=1, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="记录编号:", font=self.font_1).grid(row=1, column=0, sticky=tk.W)
        self.Test_ID = tk.Entry(self.gbNumber, width=10, font=self.font_1)
        self.Test_ID.grid(row=1, column=1, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="温度值:", font=self.font_1).grid(row=2, column=0, sticky=tk.W)
        self.Temp_Val = tk.Entry(self.gbNumber, width=10, font=self.font_1)
        self.Temp_Val.grid(row=2, column=1, padx=2, sticky=tk.NW)
        self.Pressure_val1 = tk.IntVar()
        self.Pressure_val2 = tk.IntVar()
        self.Pressure_val3 = tk.IntVar()
        self.Pressure_val4 = tk.IntVar()
        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力1:", font=self.font_1).grid(row=0, column=2, sticky=tk.W)
        self.Pressure_val1_entry = tk.Entry(self.gbNumber, width=10, font=self.font_1, textvariable=self.Pressure_val1)
        self.Pressure_val1_entry.grid(row=0, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力2:", font=self.font_1).grid(row=1, column=2, sticky=tk.W)
        self.Pressure_val2_entry = tk.Entry(self.gbNumber, width=10, font=self.font_1, textvariable=self.Pressure_val2)
        self.Pressure_val2_entry.grid(row=1, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力3:", font=self.font_1).grid(row=2, column=2, sticky=tk.W)
        self.Pressure_val3_entry = tk.Entry(self.gbNumber, width=10, font=self.font_1, textvariable=self.Pressure_val3)
        self.Pressure_val3_entry.grid(row=2, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力4:", font=self.font_1).grid(row=3, column=2, sticky=tk.W)
        self.Pressure_val4_entry = tk.Entry(self.gbNumber, width=10, font=self.font_1, textvariable=self.Pressure_val4)
        self.Pressure_val4_entry.grid(row=3, column=3, padx=2, sticky=tk.NW)
        # ----------------------------------------------------------------
        self.btnWriteCtrl = tk.Button(self.gbNumber, text='写入', font=self.font_1,
                                      command=self.btn_write_click)
        self.btnWriteCtrl.grid(row=3, column=0, sticky=tk.NW)
        self.btnReadCtrl = tk.Button(self.gbNumber, text='读取', font=self.font_1,
                                     command=self.btn_read_click)
        self.btnReadCtrl.grid(row=3, column=1, sticky=tk.NW)

    def graph_frame_start(self):
        self.gbGraph = tk.LabelFrame(self._dev_frame, text="曲线图")
        self.gbGraph.grid_propagate(True)
        self.gbGraph.grid(row=1, column=1, rowspan=2, columnspan=3, sticky=tk.NSEW)

    def gettime(self):
        self.time = time.localtime()
        self.strvTime.set("Time: " + time.strftime("%Y-%m-%d %H:%M:%S", self.time))

        self.after(1000, self.gettime)

    def to_minutes(self, x, pos):
        'Converts seconds to minutes'

        return '%1.0f' % (x * 60)

    def start_thread(self):
        """
        启动表格线程
        """

        self.folder_name = filedialog.askdirectory() + "/" + time.strftime("%Y%m%d_%H%M%S", self.open_time)
        if not os.path.exists(self.folder_name):
            os.mkdir(self.folder_name)
        self.shelf_file = os.path.join(self.folder_name, 'shelf')

        self.thread = threading.Thread(target=self.pressure_frame_thread)
        self.thread.daemon = True
        self.thread.start()

    def pressure_frame_thread(self):
        """

        """
        # 获取压力数据并更新图形
        while True:
            if not self.is_open:
                print("Pressure")
                break
            pressure = self.get_pressure()  # 获取压力数据
            self.y.append(pressure)
            self.x.append(len(self.y))
            self.line.set_xdata(self.x)
            self.line.set_ydata(self.y)
            self.fig.canvas.draw_idle()
            # 更新图形
            try:
                with shelve.open(self.shelf_file) as s:
                    s['Pressure'] = self.y
                    s['Time'] = time.strftime("%Y-%m-%d %H:%M:%S", self.time)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", "写入数据失败")
                self.btn_open_click()
            time.sleep(0.3)

    def call_move(self, event):
        """

        :param event:
        :return:
        """
        # print(mPress)
        if event.name == 'button_press_event':
            axtemp = event.inaxes
            if axtemp and event.button == 1:
                self.mPress = True
                self.start_x = event.xdata
                self.start_y = event.ydata
        elif event.name == 'button_release_event':
            axtemp = event.inaxes
            if axtemp and event.button == 1:
                self.mPress = False
        elif event.name == 'motion_notify_event':
            axtemp = event.inaxes
            if axtemp and event.button == 1 and self.mPress:
                x_min, x_max = axtemp.get_xlim()
                y_min, y_max = axtemp.get_ylim()
                w = x_max - x_min
                h = y_max - y_min
                # 移动
                mx = event.xdata - self.start_x
                my = event.ydata - self.start_y
                # 注意这里， -mx,  因为下一次 motion事件的坐标，已经是在本次做了移动之后的坐标系了，所以要体现出来
                # start_x=event.xdata-mx  start_x=event.xdata-(event.xdata-start_x)=start_x, 没必要再赋值了
                # start_y=event.ydata-my
                # print(mx,my,x_min,y_min,w,h)
                axtemp.set(xlim=(x_min - mx, x_min - mx + w))
                axtemp.set(ylim=(y_min - my, y_min - my + h))
                self.fig.canvas.draw_idle()  # 绘图动作实时反映在图像上
        return

    def call_scroll(self, event):
        """

        :param event:
        """
        axtemp = event.inaxes
        # 计算放大缩小后， xlim 和ylim
        if axtemp:
            x_min, x_max = axtemp.get_xlim()
            y_min, y_max = axtemp.get_ylim()
            w = x_max - x_min
            h = y_max - y_min
            curx = event.xdata
            cury = event.ydata
            curXposition = (curx - x_min) / w
            curYposition = (cury - y_min) / h
            if event.button == 'down':
                w *= 1.1
                h *= 1.1
            elif event.button == 'up':
                w /= 1.1
                h /= 1.1
            # print(curXposition, curYposition)
            newx = curx - w * curXposition
            newy = cury - h * curYposition
            axtemp.set(xlim=(newx, newx + w))
            axtemp.set(ylim=(newy, newy + h))
            self.fig.canvas.draw_idle()  # 绘图动作实时反映在图像上

    def show_data(self):
        self.IntVarpressure.set(int(self.y[0]))

    def btn_read_click(self):
        folder_name = filedialog.askdirectory()
        shelf_file = os.path.join(folder_name, 'shelf')
        if folder_name == '':
            messagebox.showerror("错误", "请选择文件")
            return
        with shelve.open(shelf_file) as s:
            self.Tank_ID.delete(0, tk.END)
            self.Tank_ID.insert(0, s['Tank_ID'])
            self.Test_ID.delete(0, tk.END)
            self.Test_ID.insert(0, s['Test_ID'])
            self.Temp_Val.delete(0, tk.END)
            self.Temp_Val.insert(0, s['Temp_Val'])
            self.Pressure_val1.set(s['Pressure_val1'])
            self.Pressure_val2.set(s['Pressure_val2'])
            self.Pressure_val3.set(s['Pressure_val3'])
            self.Pressure_val4.set(s['Pressure_val4'])
            pressure = s['Pressure']

        self.line.set_xdata(self.x)
        self.line.set_ydata(self.y)
        self.fig.canvas.draw_idle()


    def btn_write_click(self):

        if self.Tank_ID.get() == '' or self.Test_ID.get() == '' or self.Temp_Val.get() == '' or self.Pressure_val1.get() == '' or self.Pressure_val2.get() == '' or self.Pressure_val3.get() == '' or self.Pressure_val4.get() == '':
            messagebox.showerror("错误", "请输入完整信息")
            return

        folder_name = filedialog.askdirectory()
        shelf_file = os.path.join(folder_name, 'shelf')
        with shelve.open(shelf_file) as s:
            s['Tank_ID'] = self.Tank_ID.get()
            s['Test_ID'] = self.Test_ID.get()
            s['Temp_Val'] = self.Temp_Val.get()
            s['Pressure_val1'] = self.Pressure_val1.get()
            s['Pressure_val2'] = self.Pressure_val2.get()
            s['Pressure_val3'] = self.Pressure_val3.get()
            s['Pressure_val4'] = self.Pressure_val4.get()

    def create_file(self, filename):
        with open(filename, 'a', newline='') as f:
            pass

    def get_pressure(self):
        return random.randint(0, 10)

    def btn_open_click(self):
        """

        """
        if self.is_open:
            self.is_open = False
            self.strvDevCtrl.set("打开")
        else:
            self.is_open = True
            self.strvDevCtrl.set("关闭")
            try:
                self.start_thread()
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", "启动失败")

    def btn_1_click(self):
        self._set_btn_(self.btnReliefValveCtrl, self.strvReliefValveCtrl, 0)

    def btn_2_click(self):
        self._set_btn_(self.btnHighPressureCtrl, self.strvHighPressureCtrl, 1)

    def btn_3_click(self):
        self._set_btn_(self.btnPressureWaterCtrl, self.strvPressureWaterCtrl, 2)

    def _set_btn_(self, btn, btn_string, num):
        if self.btn_is_open[num]:
            btn['bg'] = 'green'
            self.btn_is_open[num] = False
            btn_string.set("打开")
        else:
            btn['bg'] = 'red'
            self.btn_is_open[num] = True
            btn_string.set("关闭")


def main():
    """
    主函数
    """
    demo = Widgets()
    demo.mainloop()


if __name__ == '__main__':
    main()
