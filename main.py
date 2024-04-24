# -*- coding: UTF-8 -*-
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

DEBUG = True

logger.add("log.log", rotation="1 week", retention="10 days", level="INFO")


class SerialPort:
    def __init__(self):
        self.ser = serial.Serial()
        self.ser.port = ''
        self.ser.baudrate = 115200
        self.ser.bytesize = 8
        self.ser.stopbits = 1
        self.ser.timeout = 10
        self.ser.parity = "N"
        self.data_queue = queue.Queue()
        self.port_list = []

    def get_port(self):
        self.port_list = list(serial.tools.list_ports.comports())
        if len(self.port_list) == 0:
            return None
        return self.port_list

    @logger.catch
    def connect(self, port, baudrate, stopbits, parity, bytesize):
        logger.info("连接串口")
        try:
            self.client = ModbusSerialClient(method='rtu', port=port, baudrate=baudrate, stopbits=stopbits,
                                             parity=parity,
                                             bytesize=bytesize)
            self.client.connect()
        except:
            raise Exception("连接失败")

    def disconnect(self):
        self.client.disconnect()

    @logger.catch
    def read_modbus_rtu(self, slave_id=1, addr=0x004, count=1):
        logger.info("读取数据")
        result = self.client.read_holding_registers(addr, count, unit=slave_id)
        if result.isError():
            return 0
        else:
            return result.registers[0]

    def get_data(self):
        return self.data_queue.get()


class MouseBinding:
    """

    """
    def __init__(self, ax, fig):
        self.ax = ax
        self.fig = fig
        print('init')
        self.scroll = self.ax.figure.canvas.mpl_connect('scroll_event', self.call_scroll)
        self.cidpress = self.ax.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.ax.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.ax.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        self.call_move(event)

    def on_release(self, event):
        self.call_move(event)

    def on_motion(self, event):
        self.call_move(event)

    def call_move(self, event):
        """

        :param event:
        :return:
        """
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
            newx = curx - w * curXposition
            newy = cury - h * curYposition
            axtemp.set(xlim=(newx, newx + w))
            axtemp.set(ylim=(newy, newy + h))
            self.fig.canvas.draw_idle()  # 绘图动作实时反映在图像上


class shelve_file:
    def __init__(self, shelf_file):
        self.shelf_file = shelf_file

    def write_data(self, data):
        with shelve.open(self.shelf_file) as s:
            s['data'] = data


class Widgets(tk.Tk, MouseBinding, SerialPort):
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
        self.geometry("1600x1000")
        self.resizable(False, False)
        self.open_time = time.localtime()
        self.data_queue = queue.Queue()
        self.x = []  # x轴数据
        self.y = []
        self.is_open = False
        self.font_1 = font.Font(family="bold", size=16)
        self.font_2 = font.Font(family="bold", size=20)
        SerialPort.__init__(self)
        self.generate_widgets()
        MouseBinding.__init__(self, self.ax, self.fig)

    def generate_widgets(self):
        """
        生成窗口部件
        """
        tk.Tk.protocol(self, 'WM_DELETE_WINDOW', self.quit)
        self._dev_frame = tk.Frame(self)
        self._dev_frame.grid(row=0, column=0, sticky=tk.NW)
        self.graph_frame_start()
        self.device_frame_start()
        self.copyright_frame_start()
        self.number_frame_start()
        self.data_frame_start()
        self.btn_frame_start()
        self.table_frame_start()

    def table_frame_start(self):
        """

        """
        self.mPress = False
        self.start_x = 0
        self.start_y = 0
        self.fig, self.ax = plt.subplots(figsize=(20, 8), dpi=80)  # 创建一个图形和一个坐标轴

        self.fig.subplots_adjust(left=0.15, right=0.99, bottom=0.1, top=0.95, wspace=0.2, hspace=0.2)

        self.line, = self.ax.plot(self.x, self.y)
        self.ax.grid(True)  # 显示网格
        self.ax.set_title('Pressure vs Time')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Pressure (Pa)')
        self.ax.fill_between(self.x, self.y, 100, color='white')
        self.ax.set_xlim(0, 150)
        self.ax.set_ylim(0, 10)
        # 将图形添加到tkinter窗口
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.gbGraph)  # A tk.DrawingArea.
        self.canvas.draw()  # 显示图形
        self.canvas.get_tk_widget().grid(row=2, column=2, sticky=tk.NW)  # 显示位置

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
        self.cmbDevType = ttk.Combobox(self.gbDevConnect, width=17, font=self.font_1, state="readonly")
        self.cmbDevType.grid(row=0, column=1, sticky=tk.NW)
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
        # self.gbDevCopyRight.grid(row=1, column=0, padx=2, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Author: Liu Bingqian").grid(row=2, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Email: lbq08@foxmail.com").grid(row=3, column=0, sticky=tk.NW)
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, text="Version: 1.0.6").grid(row=4, column=0, sticky=tk.NW)
        # Time Label
        self.strvTime = tk.StringVar()
        tk.Label(self.gbDevCopyRight, anchor=tk.NW, textvariable=self.strvTime).grid(row=5, column=0, sticky=tk.NW)
        self.gettime()

    def data_frame_start(self):
        """

        """
        self.gbData = tk.LabelFrame(self._dev_frame, text="实时值")
        self.gbData.grid_propagate(True)
        self.gbData.grid(row=0, column=2, sticky=tk.NW)
        self.IntVarpressure = tk.DoubleVar()
        self.IntVarpressure.set(0)
        tk.Label(self.gbData, anchor=tk.NW, text="压力值:", font=self.font_1).grid(row=0, column=0, sticky=tk.NW)
        tk.Label(self.gbData, anchor=tk.NW, textvariable=self.IntVarpressure, width=3, font=self.font_1).grid(row=0,
                                                                                                              column=1,
                                                                                                              sticky=tk.NW)
        # self.IntVartemp = tk.DoubleVar()
        # self.IntVartemp.set(0)
        # tk.Label(self.gbData, anchor=tk.NW, text="温度值:", font=self.font_1).grid(row=1, column=0, sticky=tk.NW)
        # tk.Label(self.gbData, anchor=tk.NW, textvariable=self.IntVartemp, font=self.font_1).grid(row=1, column=1,
        #                                                                                          sticky=tk.NW)

    def btn_frame_start(self):
        """

        """
        self.gbBtn = tk.LabelFrame(self._dev_frame, height=100, width=200, text="按钮")
        # TODO 增加按钮
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
        """

        """
        self.gbNumber = tk.LabelFrame(self._dev_frame, height=100, width=200, text="编号输入")
        self.gbNumber.grid_propagate(True)
        self.gbNumber.grid(row=0, column=1, sticky=tk.NW)
        # columnspan=2, rowspan=2,
        self.Process_Val = tk.DoubleVar()
        self.Test_ID = tk.StringVar()
        self.Temp_val = tk.DoubleVar()
        self.Tank_ID1 = tk.StringVar()
        self.Tank_ID2 = tk.StringVar()
        self.Tank_ID3 = tk.StringVar()
        self.Tank_ID4 = tk.StringVar()
        self.Holding_time = tk.DoubleVar()
        tk.Label(self.gbNumber, anchor=tk.W, text="实验压力:", font=self.font_1).grid(row=0, column=0, sticky=tk.W)
        self.Process_val_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Process_Val)
        self.Process_val_entry.grid(row=0, column=1, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="记录编号:", font=self.font_1).grid(row=1, column=0, sticky=tk.W)
        self.Test_ID_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Test_ID)
        self.Test_ID_entry.grid(row=1, column=1, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="温度值:", font=self.font_1).grid(row=2, column=0, sticky=tk.W)
        self.Temp_val_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Temp_val)
        self.Temp_val_entry.grid(row=2, column=1, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号1:", font=self.font_1).grid(row=0, column=2, sticky=tk.W)
        self.Pressure_val1_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Tank_ID1)
        self.Pressure_val1_entry.grid(row=0, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号2:", font=self.font_1).grid(row=1, column=2, sticky=tk.W)
        self.Pressure_val2_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Tank_ID2)
        self.Pressure_val2_entry.grid(row=1, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号3:", font=self.font_1).grid(row=2, column=2, sticky=tk.W)
        self.Pressure_val3_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Tank_ID3)
        self.Pressure_val3_entry.grid(row=2, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="钢瓶编号4:", font=self.font_1).grid(row=3, column=2, sticky=tk.W)
        self.Pressure_val4_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Tank_ID4)
        self.Pressure_val4_entry.grid(row=3, column=3, padx=2, sticky=tk.NW)
        tk.Label(self.gbNumber, anchor=tk.W, text="保压时间:", font=self.font_1).grid(row=4, column=2, sticky=tk.W)
        self.Holding_time_entry = tk.Entry(self.gbNumber, width=17, font=self.font_1, textvariable=self.Holding_time)
        self.Holding_time_entry.grid(row=4, column=3, padx=2, sticky=tk.NW)
        # ----------------------------------------------------------------
        self.btnWriteCtrl = tk.Button(self.gbNumber, text='写入文件', font=self.font_1,
                                      command=self.btn_write_click)
        self.btnWriteCtrl.grid(row=3, column=0, sticky=tk.NW)
        self.btnReadCtrl = tk.Button(self.gbNumber, text='读取文件', font=self.font_1,
                                     command=self.btn_read_click)
        self.btnReadCtrl.grid(row=3, column=1, sticky=tk.NW)
        self.btnSaveCtrl = tk.Button(self.gbNumber, text='保存图片', font=self.font_1,
                                     command=self.btn_save_click)
        self.btnSaveCtrl.grid(row=4, column=0, sticky=tk.NW)

    def graph_frame_start(self):
        """

        """
        self.gbGraph = tk.LabelFrame(self._dev_frame, text="曲线图")
        self.gbGraph.grid_propagate(True)
        self.gbGraph.grid(row=1, column=0, rowspan=8, columnspan=8, sticky=tk.NSEW)

    def gettime(self):
        """

        """
        self.cmbDevType["value"] = [comport.name for comport in self.get_port()]
        self.time = time.localtime()
        self.strvTime.set("Time: " + time.strftime("%Y-%m-%d %H:%M:%S", self.time))
        self.after(1000, self.gettime)

    def to_minutes(self, x, pos):
        'Converts seconds to minutes'
        return '%1.0f' % (x * 60)

    @logger.catch
    def start_thread(self):
        """
        启动表格线程
        """

        self.thread = threading.Thread(target=self.pressure_frame_thread)
        self.thread.daemon = True
        self.thread.start()
        logger.debug("启动表格线程")

    def add_text_outside_axes(self, x, y, text):
        self.fig.text(x, y, text, fontsize=12, transform=self.fig.transFigure)
        self.fig.canvas.draw()

    def stop_thread(self):
        """
        停止表格线程
        """
        pass

    @logger.catch
    def pressure_frame_thread(self):
        """

        """
        # 获取压力数据并更新图形
        while True:
            if not self.is_open:
                break
            try:
                pressure = self.get_pressure()  # 获取压力数据
                self.IntVarpressure.set(pressure)
                self.y.append(pressure)
                self.x.append(len(self.y))
                self.line.set_xdata(self.x)
                self.line.set_ydata(self.y)
                self.fig.canvas.draw_idle()
                # 更新图形
            except Exception as e:
                self.stop_thread()
                logger.error(e)
                self.btn_open_click()
                messagebox.showerror("错误", "写入数据失败")
                raise Exception("获取数据失败")
            time.sleep(1)

    @logger.catch
    def btn_read_click(self):
        folder_name = filedialog.askdirectory()
        shelf_file = os.path.join(folder_name, 'shelf')
        if folder_name == '':
            messagebox.showerror("错误", "请选择文件")
            return
        with shelve.open(shelf_file) as s:
            self.Process_Val.set(s['Process_Val'])
            self.Test_ID.set(s['Test_ID'])
            self.Temp_val.set(s['Temp_val'])
            self.Tank_ID1.set(s['Tank_ID1'])
            self.Tank_ID2.set(s['Tank_ID2'])
            self.Tank_ID3.set(s['Tank_ID3'])
            self.Tank_ID4.set(s['Tank_ID4'])
            self.Holding_time.set(s['Holding_time'])

            pressure = s['Pressure']
            self.add_text_outside_axes(0, 0.9, 'Process_Val: ' + str(s['Process_Val']))
            self.add_text_outside_axes(0, 0.8, 'Test_ID: ' + str(s['Test_ID']))
            self.add_text_outside_axes(0, 0.7, 'Temp_val: ' + str(s['Temp_val']))
            self.add_text_outside_axes(0, 0.6, 'Tank_ID1: ' + str(s['Tank_ID1']))
            self.add_text_outside_axes(0, 0.5, 'Tank_ID2: ' + str(s['Tank_ID2']))
            self.add_text_outside_axes(0, 0.4, 'Tank_ID3: ' + str(s['Tank_ID3']))
            self.add_text_outside_axes(0, 0.3, 'Tank_ID4: ' + str(s['Tank_ID4']))
            self.add_text_outside_axes(0, 0.2, 'Holding_time: ' + str(s['Holding_time']))
            self.add_text_outside_axes(0, 0.1, 'Time: ' + s['Time'])

        self.ax.clear()
        self.ax.plot(pressure)
        self.fig.canvas.draw_idle()
        messagebox.showinfo('信息', '读取成功！')

    @logger.catch
    def btn_write_click(self):

        if self.Temp_val.get() == '' or self.Tank_ID1.get() == '' or self.Tank_ID2.get() == '' or self.Tank_ID4.get() == '' or self.Tank_ID4.get() == '':
            messagebox.showerror("错误", "请输入完整信息")
            return
        self.floder_generate()
        # writeback
        with shelve.open(self.shelf_file) as s:
            s['Pressure'] = self.y
            s['Time'] = time.strftime("%Y-%m-%d %H:%M:%S", self.time)
            s['Process_Val'] = self.Process_Val.get()
            s['Test_ID'] = str(self.Test_ID.get())
            s['Temp_val'] = self.Temp_val.get()
            s['Tank_ID1'] = self.Tank_ID1.get()
            s['Tank_ID2'] = self.Tank_ID2.get()
            s['Tank_ID3'] = self.Tank_ID3.get()
            s['Tank_ID4'] = self.Tank_ID4.get()
            s['Holding_time'] = self.Holding_time.get()
            self.add_text_outside_axes(0, 0.9, 'Process_Val: ' + str(self.Process_Val.get()))
            self.add_text_outside_axes(0, 0.8, 'Test_ID: ' + self.Test_ID.get())
            self.add_text_outside_axes(0, 0.7, 'Temp_val: ' + str(self.Temp_val.get()))
            self.add_text_outside_axes(0, 0.6, 'Tank_ID1: ' + self.Tank_ID1.get())
            self.add_text_outside_axes(0, 0.5, 'Tank_ID2: ' + self.Tank_ID2.get())
            self.add_text_outside_axes(0, 0.4, 'Tank_ID3: ' + self.Tank_ID3.get())
            self.add_text_outside_axes(0, 0.3, 'Tank_ID4: ' + self.Tank_ID4.get())
            self.add_text_outside_axes(0, 0.2, 'Holding_time: ' + str(self.Holding_time.get()))
            self.add_text_outside_axes(0, 0.1, 'Time: ' + time.strftime("%Y-%m-%d %H:%M:%S", self.time))
        logger.info(self.shelf_file)
        logger.info(self.folder_name)
        messagebox.showinfo('信息', '写入成功！')



    @logger.catch
    def get_pressure(self):
        # self.read_modbus_rtu()
        return random.randint(0, 10)

    def floder_generate(self):
        try:
            self.folder_name = filedialog.askdirectory() + "/" + time.strftime("%Y%m%d_",
                                                                               self.open_time) + self.Test_ID.get()
            if not os.path.exists(self.folder_name):
                os.mkdir(self.folder_name)
            self.shelf_file = os.path.join(self.folder_name, 'shelf')
        except:
            raise Exception("文件夹生成失败")

    @logger.catch
    def btn_open_click(self):
        """

        """
        if self.is_open:
            self.is_open = False
            self.strvDevCtrl.set("开始记录")
        else:
            try:
                if self.Test_ID.get() == '':
                    messagebox.showerror("错误", "请输入记录编号")
                    return
                # self.floder_generate()
                self.connect(self.cmbDevType.get(), 115200, 1, "N", 8)
                self.is_open = True
                self.strvDevCtrl.set("停止记录")
                self.start_thread()
                messagebox.showinfo('信息', '启动成功！')
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", "启动失败")

    def btn_1_click(self):
        self._set_btn_(self.btnReliefValveCtrl, self.strvReliefValveCtrl, 0)

    def btn_2_click(self):
        self._set_btn_(self.btnHighPressureCtrl, self.strvHighPressureCtrl, 1)

    def btn_3_click(self):
        self._set_btn_(self.btnPressureWaterCtrl, self.strvPressureWaterCtrl, 2)

    def btn_save_click(self):
        filename = filedialog.asksaveasfilename(defaultextension=".png")
        if filename:
            self.fig.savefig(filename)

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
