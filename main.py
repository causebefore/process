# -*- coding: UTF-8 -*-
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from loguru import logger
import os
import serial
import matplotlib.pyplot as plt
import numpy as np
import csv
import random

PATH = os.getcwd()

open_time = time.localtime()


class Widgets(tk.Tk):
    """
    1. 该类继承了tk.Tk类，因此可以直接使用Tk类的方法
    """

    def __init__(self):
        tk.Tk.__init__(self)
        self.ax = None
        self.fig = None
        self.strvTime = None
        self.thread = None
        self.title("串口调试助手")
        self.geometry("1000x800")
        self.resizable(False, False)

        self.data_queue = queue.Queue()
        tk.Tk.protocol(self, 'WM_DELETE_WINDOW', self.quit)
        self.is_open = False
        self._dev_frame = tk.Frame(self)
        self._dev_frame.grid(row=0, column=0, padx=1, pady=1, sticky=tk.NW)
        self.device_frame_start()
        self.copyright_frame_start()
        self.number_frame_start()
        self.graph_frame_start()
        self.create_widgets()
        self.start_thread()
        self.mPress = False
        self.start_x = 0
        self.start_y = 0

    def device_frame_start(self):
        """
        设备选择框架
        """
        # Device Choose Frame
        self.gbDevConnect = tk.LabelFrame(self._dev_frame, height=100, width=200, text="设备选择")
        self.gbDevConnect.grid_propagate(True)
        self.gbDevConnect.grid(row=0, column=0, padx=2, pady=2, sticky=tk.NW)
        # Device Information Frame
        tk.Label(self.gbDevConnect, text="串口号:").grid(row=0, column=0, sticky=tk.NW)
        self.cmbDevType = ttk.Combobox(self.gbDevConnect, width=13, state="readonly")
        self.cmbDevType.grid(row=0, column=1, sticky=tk.NW)
        self.cmbDevType["value"] = ["com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "com10"]
        self.cmbDevType.current(0)
        self.strvDevCtrl = tk.StringVar()
        self.strvDevCtrl.set("打开")
        self.btnDevCtrl = ttk.Button(self.gbDevConnect, textvariable=self.strvDevCtrl, command=self.btn_open_click)
        self.btnDevCtrl.grid(row=2, column=0, columnspan=2, pady=2, sticky=tk.E)

    def copyright_frame_start(self):
        """
        版权信息框架
        """
        # CopyRight Frame
        self.gbDevCopyRight = tk.LabelFrame(self._dev_frame, height=100, width=200, text="版权信息")
        self.gbDevCopyRight.grid_propagate(True)
        self.gbDevCopyRight.grid(row=1, column=0, padx=2, pady=2, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Author: Liu Bingqian").grid(row=2, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Email: lbq08@foxmail.com").grid(row=3, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Version: 1.0.6").grid(row=4, column=0, sticky=tk.NW)
        # Time Label
        self.strvTime = tk.StringVar()
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, textvariable=self.strvTime).grid(row=5, column=0, sticky=tk.NW)
        self.gettime()

    def create_widgets(self):
        pass

    def gettime(self):
        self.strvTime.set("Time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        self.after(1000, self.gettime)

    def number_frame_start(self):
        self.gbNumber = tk.LabelFrame(self._dev_frame, height=100, width=200, text="编号输入")
        self.gbNumber.grid_propagate(True)
        self.gbNumber.grid(row=0, column=1, columnspan=2, padx=2, pady=2, sticky=tk.NW)

        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号:").grid(row=0, column=0, sticky=tk.W)
        self.Tank_ID = tk.Entry(self.gbNumber, width=20)
        self.Tank_ID.grid(row=0, column=1, columnspan=2, padx=2, pady=2, sticky=tk.NW)

        tk.Label(self.gbNumber, anchor=tk.W, text="记录编号:").grid(row=1, column=0, sticky=tk.W)
        self.Test_ID = tk.Entry(self.gbNumber, width=20)
        self.Test_ID.grid(row=1, column=1, columnspan=2, padx=2, pady=2, sticky=tk.NW)

        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力:").grid(row=2, column=0, sticky=tk.W)
        self.Pressure_val = tk.Entry(self.gbNumber, width=20)
        self.Pressure_val.grid(row=2, column=1, columnspan=2, padx=2, pady=2, sticky=tk.NW)
        self.strvWrite = tk.StringVar()
        self.strvWrite.set("写入")
        self.btnDevCtrl = ttk.Button(self.gbNumber, textvariable=self.strvWrite, command=self.btn_write_click)
        self.btnDevCtrl.grid(row=3, column=0, columnspan=2, pady=2, sticky=tk.NW)



    def graph_frame_start(self):
        self.gbGraph = tk.LabelFrame(self._dev_frame, height=100, width=200, text="曲线图")
        self.gbGraph.grid_propagate(True)
        self.gbGraph.grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky=tk.NW)


    def start_thread(self):
        """
        启动表格线程
        """
        self.fig, self.ax = plt.subplots(figsize=(4, 4),dpi=80)  # 创建一个图形和一个坐标轴

        self.fig.subplots_adjust(left=0.2, right=0.9, top=0.9, bottom=0.2)  # 调整图形的边距
        self.ax.grid(True)  # 显示网格
        self.fig.canvas.mpl_connect('scroll_event', self.call_scroll)  # 绑定鼠标滚轮事件
        self.fig.canvas.mpl_connect('button_press_event', self.call_move)  # 绑定鼠标按下事件
        self.fig.canvas.mpl_connect('button_release_event', self.call_move)  # 绑定鼠标松开事件
        self.fig.canvas.mpl_connect('motion_notify_event', self.call_move)  # 绑定鼠标移动事件

        self.x = np.arange(60 * 60 * 2)  # x轴数据
        self.y = np.zeros(60 * 60 * 2)  # y轴数据

        self.line, = self.ax.plot(self.x, self.y)
        self.ax.set_title('Pressure vs Time')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Pressure')
        # 将图形添加到tkinter窗口
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.gbGraph)  # A tk.DrawingArea.
        self.canvas.draw()  # 显示图形
        self.ax.fill_between(self.x, self.y, 100, color='white')
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 60)
        self.canvas.get_tk_widget().grid(row=1, column=1, sticky=tk.NW)  # 显示位置
        self.thread = threading.Thread(target=self.pressure_frame_thread)
        self.thread.daemon = True
        self.thread.start()

    def pressure_frame_thread(self):
        """

        """
        # 获取压力数据并更新图形
        while True:
            pressure = self.get_pressure()  # 获取压力数据

            # 更新图形
            self.y = np.roll(self.y, 1)  # 将数组中的元素向前滚动一个位置
            self.y[1] = pressure  # 在数组的最后一个位置添加新的数据
            self.line.set_ydata(self.y)
            self.ax.relim()  # 重新计算坐标轴的界限
            self.ax.autoscale_view()  # 更新坐标轴的界限
            self.canvas.draw()  # 重绘图形
            with open(time.strftime("%Y%m%d_%H%M%S", open_time) + '_PRESSURE.csv', 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                writer.writerow(data)
            time.sleep(1)

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
            print(curXposition, curYposition)
            newx = curx - w * curXposition
            newy = cury - h * curYposition
            axtemp.set(xlim=(newx, newx + w))
            axtemp.set(ylim=(newy, newy + h))
            self.fig.canvas.draw_idle()  # 绘图动作实时反映在图像上

    def btn_write_click(self):
        data = {
            'Tank_ID': self.Tank_ID.get(),
            'Test_ID': self.Test_ID.get(),
            'Pressure_val': self.Pressure_val.get(),
            'Time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }

        # 写入CSV文件
        with open(time.strftime("%Y%m%d_%H%M%S", open_time) + '_OUTPUT.csv', 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writerow(data)

    def get_pressure(self):
        return random.randint(0, 40)

    def get_temperature(self):
        return random.randint(0, 40)

    def btn_open_click(self):
        """

        """
        try:
            if self.is_open:
                self.close_serial()
            else:
                self.open_serial()
        except Exception as e:
            logger.error(e)
            messagebox.showerror("错误", e)


def main():
    """
    主函数
    """
    demo = Widgets()
    demo.mainloop()


if __name__ == '__main__':
    main()
