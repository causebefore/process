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
import shelve
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient




DEBUG = True
PATH = os.getcwd()

# setup.py import line


VERSION = "1.0.6"
EMAIL = 'lbqdlbq08@outlook.com'
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
        self.read_error = False

    def get_port(self):
        self.port_list = list(serial.tools.list_ports.comports())
        if len(self.port_list) == 0:
            return []
        return self.port_list

    @logger.catch
    def connect(self, port, baudrate, stopbits, parity, bytesize):
        logger.info("连接串口")
        try:
            self.client = ModbusSerialClient(method='rtu', port=port, baudrate=baudrate, stopbits=stopbits,
                                             parity=parity,
                                             bytesize=bytesize)
            self.client.connect()
        except Exception as e:
            raise Exception(f"连接失败: {e}")

    def read_modbus_rtu(self, slave_id=1, addr=0x004, count=1):
        logger.info("读取数据")
        self.result = self.client.read_holding_registers(address=addr, count=count, slave=slave_id)
        if self.result.isError():
            self.read_error = True
            return 0
        else:
            self.read_error = False
            logger.debug(self.result.registers[0])
            return self.result.registers[0]

    def is_error(self):
        return self.read_error


class MouseBinding:
    """图表鼠标交互：拖拽平移与滚轮缩放"""

    def __init__(self, ax, fig):
        self.ax = ax
        self.fig = fig
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        logger.debug('MouseBinding init')
        self.ax.figure.canvas.mpl_connect('scroll_event', self._handle_scroll)
        self.ax.figure.canvas.mpl_connect('button_press_event', self._handle_mouse_event)
        self.ax.figure.canvas.mpl_connect('button_release_event', self._handle_mouse_event)
        self.ax.figure.canvas.mpl_connect('motion_notify_event', self._handle_mouse_event)

    def _handle_mouse_event(self, event):
        """处理鼠标按下/释放/移动事件，实现拖拽平移"""
        if event.name == 'button_press_event':
            active_axes = event.inaxes
            if active_axes and event.button == 1:
                self._is_dragging = True
                self._drag_start_x = event.xdata
                self._drag_start_y = event.ydata
        elif event.name == 'button_release_event':
            active_axes = event.inaxes
            if active_axes and event.button == 1:
                self._is_dragging = False
        elif event.name == 'motion_notify_event':
            active_axes = event.inaxes
            if active_axes and event.button == 1 and self._is_dragging:
                x_min, x_max = active_axes.get_xlim()
                y_min, y_max = active_axes.get_ylim()
                w = x_max - x_min
                h = y_max - y_min
                mx = event.xdata - self._drag_start_x
                my = event.ydata - self._drag_start_y
                # 注意这里， -mx,  因为下一次 motion事件的坐标，已经是在本次做了移动之后的坐标系了，所以要体现出来
                # start_x=event.xdata-mx  start_x=event.xdata-(event.xdata-start_x)=start_x, 没必要再赋值了
                active_axes.set(xlim=(x_min - mx, x_min - mx + w))
                active_axes.set(ylim=(y_min - my, y_min - my + h))
                self.fig.canvas.draw_idle()

    def _handle_scroll(self, event):
        """处理滚轮事件，实现以光标为中心的缩放"""
        active_axes = event.inaxes
        if active_axes:
            x_min, x_max = active_axes.get_xlim()
            y_min, y_max = active_axes.get_ylim()
            w = x_max - x_min
            h = y_max - y_min
            cursor_x = event.xdata
            cursor_y = event.ydata
            cursor_x_ratio = (cursor_x - x_min) / w
            cursor_y_ratio = (cursor_y - y_min) / h
            if event.button == 'down':
                w *= 1.1
                h *= 1.1
            elif event.button == 'up':
                w /= 1.1
                h /= 1.1
            new_x = cursor_x - w * cursor_x_ratio
            new_y = cursor_y - h * cursor_y_ratio
            active_axes.set(xlim=(new_x, new_x + w))
            active_axes.set(ylim=(new_y, new_y + h))
            self.fig.canvas.draw_idle()


class ShelveFile:
    def __init__(self, shelf_file):
        self.shelf_file = shelf_file

    def write_data(self, data):
        with shelve.open(self.shelf_file) as s:
            s['data'] = data


class PressureTestApp(tk.Tk, MouseBinding, SerialPort):
    """压力测试系统主窗口"""

    def __init__(self):
        tk.Tk.__init__(self)
        self._valve_states = [False, False, False, False]
        self.ax = None
        self.fig = None
        self._time_var = None
        self._thread = None
        self.process_data = []
        self.title("压力测试系统 " + VERSION + ' Email:' + EMAIL)
        self.geometry("1600x1000")
        self.resizable(False, False)
        self._start_time = time.localtime()
        self.data_queue = queue.Queue()
        self._x_data = []
        self._y_data = []
        self._is_recording = False
        self._font_normal = font.Font(family="bold", size=16)
        self._font_large = font.Font(family="bold", size=20)
        SerialPort.__init__(self)
        self._init_widgets()
        MouseBinding.__init__(self, self.ax, self.fig)

    def _init_widgets(self):
        """生成窗口部件"""
        tk.Tk.protocol(self, 'WM_DELETE_WINDOW', self._on_closing)
        self._main_frame = tk.Frame(self)
        self._main_frame.grid(row=0, column=0, sticky=tk.NW)
        self._init_graph_frame()
        self._init_device_frame()
        self._init_copyright_frame()
        self._init_number_frame()
        self._init_data_frame()
        self._init_button_frame()
        self._init_chart_frame()

    def _init_chart_frame(self):
        """初始化图表区域"""
        self.fig, self.ax = plt.subplots(figsize=(20, 8), dpi=80)
        self.fig.subplots_adjust(left=0.15, right=0.99, bottom=0.1, top=0.95, wspace=0.2, hspace=0.2)

        self._line, = self.ax.plot(self._x_data, self._y_data)
        self.ax.set_title('Pressure vs Time')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Pressure (Pa)')
        self.ax.fill_between(self._x_data, self._y_data, 100, color='white')
        self.ax.set_xlim(0, 150)
        self.ax.set_ylim(0, 10)

        self._chart_canvas = FigureCanvasTkAgg(self.fig, master=self._frm_graph)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().grid(row=2, column=2, sticky=tk.NW)

    def _init_device_frame(self):
        """设备选择框架"""
        self._frm_device = tk.LabelFrame(self._main_frame, height=100, width=200, text="设备选择")
        self._frm_device.grid_propagate(True)
        self._frm_device.grid(row=0, column=0, padx=2, sticky=tk.NW)
        tk.Label(self._frm_device, text="串口号:", font=self._font_normal).grid(row=0, column=0, sticky=tk.NW)
        self._cmb_port = ttk.Combobox(self._frm_device, width=17, font=self._font_normal, state="readonly")
        self._cmb_port.grid(row=0, column=1, sticky=tk.NW)
        self._record_ctrl_var = tk.StringVar()
        self._record_ctrl_var.set("开始记录")
        self._btn_record = tk.Button(self._frm_device, width=7, font=self._font_normal,
                                     textvariable=self._record_ctrl_var, command=self._on_record_click)
        self._btn_record.grid(row=2, column=0, sticky=tk.E)

    def _init_copyright_frame(self):
        """版权信息框架"""
        self._frm_copyright = tk.LabelFrame(self._main_frame, height=100, width=200, text="版权信息")
        self._frm_copyright.grid_propagate(True)
        # self._frm_copyright.grid(row=1, column=0, sticky=tk.NW)
        tk.Label(self._frm_copyright, anchor=tk.NW, text="Author: Liu Bingqian").grid(row=2, column=0, sticky=tk.NW)
        tk.Label(self._frm_copyright, anchor=tk.NW, text="Email: " + EMAIL).grid(row=3, column=0, sticky=tk.NW)
        tk.Label(self._frm_copyright, anchor=tk.NW, text="Version: " + VERSION).grid(row=4, column=0, sticky=tk.NW)
        self._time_var = tk.StringVar()
        tk.Label(self._frm_copyright, anchor=tk.NW, textvariable=self._time_var).grid(row=5, column=0, sticky=tk.NW)
        self._update_time()

    def _init_data_frame(self):
        """实时数据显示框架"""
        self._frm_data = tk.LabelFrame(self._main_frame, text="实时值")
        self._frm_data.grid_propagate(True)
        self._frm_data.grid(row=0, column=2, sticky=tk.NW)
        self._pressure_var = tk.DoubleVar()
        self._pressure_var.set(0)
        tk.Label(self._frm_data, anchor=tk.NW, text="压力值:", font=self._font_normal).grid(row=0, column=0, sticky=tk.NW)
        tk.Label(self._frm_data, anchor=tk.NW, textvariable=self._pressure_var, width=3, font=self._font_normal).grid(
            row=0, column=1, sticky=tk.NW)

    def _init_button_frame(self):
        """按钮控制框架"""
        self._frm_buttons = tk.LabelFrame(self._main_frame, height=100, width=200, text="按钮")
        self._frm_buttons.grid_propagate(True)
        self._frm_buttons.grid(row=0, column=3, sticky=tk.NW)

        tk.Label(self._frm_buttons, anchor=tk.NW, text="泄压阀控制", font=self._font_normal).grid(row=0, column=0, sticky=tk.NW)
        tk.Label(self._frm_buttons, anchor=tk.NW, text="高压泵控制", font=self._font_normal).grid(row=1, column=0, sticky=tk.NW)
        tk.Label(self._frm_buttons, anchor=tk.NW, text="高压进水控制", font=self._font_normal).grid(row=2, column=0, sticky=tk.NW)

        self._relief_valve_var = tk.StringVar()
        self._relief_valve_var.set("打开")
        self._btn_relief_valve = tk.Button(self._frm_buttons, textvariable=self._relief_valve_var, font=self._font_normal,
                                           command=self._on_relief_valve_click, bg="green")
        self._btn_relief_valve.grid(row=0, column=1, sticky=tk.E)

        self._high_pressure_var = tk.StringVar()
        self._high_pressure_var.set("打开")
        self._btn_high_pressure = tk.Button(self._frm_buttons, textvariable=self._high_pressure_var, font=self._font_normal,
                                            command=self._on_high_pressure_click, bg="green")
        self._btn_high_pressure.grid(row=1, column=1, sticky=tk.E)

        self._pressure_water_var = tk.StringVar()
        self._pressure_water_var.set("打开")
        self._btn_pressure_water = tk.Button(self._frm_buttons, textvariable=self._pressure_water_var, font=self._font_normal,
                                             command=self._on_pressure_water_click, bg="green")
        self._btn_pressure_water.grid(row=2, column=1, sticky=tk.E)

    def _init_number_frame(self):
        """编号输入框架"""
        self._frm_number = tk.LabelFrame(self._main_frame, height=100, width=200, text="编号输入")
        self._frm_number.grid_propagate(True)
        self._frm_number.grid(row=0, column=1, sticky=tk.NW)

        self._process_val = tk.DoubleVar()
        self._test_id = tk.StringVar()
        self._temp_val = tk.DoubleVar()
        self._tank_id1 = tk.StringVar()
        self._tank_id2 = tk.StringVar()
        self._tank_id3 = tk.StringVar()
        self._tank_id4 = tk.StringVar()
        self._holding_time = tk.DoubleVar()

        tk.Label(self._frm_number, anchor=tk.W, text="实验压力:", font=self._font_normal).grid(row=0, column=0, sticky=tk.W)
        self._entry_process_val = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._process_val)
        self._entry_process_val.grid(row=0, column=1, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="记录编号:", font=self._font_normal).grid(row=1, column=0, sticky=tk.W)
        self._entry_test_id = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._test_id)
        self._entry_test_id.grid(row=1, column=1, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="温度值:", font=self._font_normal).grid(row=2, column=0, sticky=tk.W)
        self._entry_temp_val = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._temp_val)
        self._entry_temp_val.grid(row=2, column=1, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="钢瓶编号1:", font=self._font_normal).grid(row=0, column=2, sticky=tk.W)
        self._entry_tank_id1 = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._tank_id1)
        self._entry_tank_id1.grid(row=0, column=3, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="钢瓶编号2:", font=self._font_normal).grid(row=1, column=2, sticky=tk.W)
        self._entry_tank_id2 = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._tank_id2)
        self._entry_tank_id2.grid(row=1, column=3, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="钢瓶编号3:", font=self._font_normal).grid(row=2, column=2, sticky=tk.W)
        self._entry_tank_id3 = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._tank_id3)
        self._entry_tank_id3.grid(row=2, column=3, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="钢瓶编号4:", font=self._font_normal).grid(row=3, column=2, sticky=tk.W)
        self._entry_tank_id4 = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._tank_id4)
        self._entry_tank_id4.grid(row=3, column=3, padx=2, sticky=tk.NW)

        tk.Label(self._frm_number, anchor=tk.W, text="保压时间:", font=self._font_normal).grid(row=4, column=2, sticky=tk.W)
        self._entry_holding_time = tk.Entry(self._frm_number, width=17, font=self._font_normal, textvariable=self._holding_time)
        self._entry_holding_time.grid(row=4, column=3, padx=2, sticky=tk.NW)
        # ----------------------------------------------------------------
        self._btn_write = tk.Button(self._frm_number, text='写入文件', font=self._font_normal,
                                    command=self._on_write_click)
        self._btn_write.grid(row=3, column=0, sticky=tk.NW)
        self._btn_read = tk.Button(self._frm_number, text='读取文件', font=self._font_normal,
                                   command=self._on_read_click)
        self._btn_read.grid(row=3, column=1, sticky=tk.NW)
        self._btn_save = tk.Button(self._frm_number, text='保存图片', font=self._font_normal,
                                   command=self._on_save_click)
        self._btn_save.grid(row=4, column=0, sticky=tk.NW)

    def _init_graph_frame(self):
        """初始化曲线图容器"""
        self._frm_graph = tk.LabelFrame(self._main_frame, text="曲线图")
        self._frm_graph.grid_propagate(True)
        self._frm_graph.grid(row=1, column=0, rowspan=8, columnspan=8, sticky=tk.NSEW)

    def _update_time(self):
        """定时更新串口列表和时间显示"""
        self._cmb_port["value"] = [comport.name for comport in self.get_port()]
        self._current_time = time.localtime()
        self._time_var.set("Time: " + time.strftime("%Y-%m-%d %H:%M:%S", self._current_time))
        self.after(1000, self._update_time)

    @logger.catch
    def _start_data_thread(self):
        """启动数据采集线程"""
        self._thread = threading.Thread(target=self._data_collection_loop)
        self._thread.daemon = True
        self._thread.start()
        logger.debug("启动数据采集线程")

    def _add_figure_text(self, x, y, text):
        """在图形区域外添加文本标注"""
        self.fig.text(x, y, text, fontsize=12, transform=self.fig.transFigure)
        self.fig.canvas.draw()

    def _stop_data_thread(self):
        """停止数据采集线程"""
        self._is_recording = False

    def _update_gui_pressure(self, pressure):
        """在主线程中更新压力相关的 GUI 控件"""
        self._pressure_var.set(pressure)
        self._y_data.append(pressure)
        self._x_data.append(len(self._y_data))
        self._line.set_xdata(self._x_data)
        self._line.set_ydata(self._y_data)
        self.fig.canvas.draw_idle()

    def _handle_thread_error(self, error_msg):
        """在主线程中处理采集线程错误"""
        logger.error(error_msg)
        self._stop_data_thread()
        self._record_ctrl_var.set("开始记录")
        messagebox.showerror("错误", "读取数据失败")

    @logger.catch
    def _data_collection_loop(self):
        """数据采集线程：循环读取压力传感器数据"""
        while self._is_recording:
            try:
                pressure = self._get_pressure()
                if self.is_error():
                    raise Exception("读取数据失败")
                self.after(0, self._update_gui_pressure, pressure)
            except Exception as e:
                self.after(0, self._handle_thread_error, str(e))
                break
            time.sleep(0.5)

    @logger.catch
    def _on_read_click(self):
        """读取文件按钮回调"""
        folder_name = filedialog.askdirectory()
        shelf_file = os.path.join(folder_name, 'shelf')

        if self._is_recording:
            messagebox.showerror("错误", "请先停止记录")
            return
        if folder_name == '':
            messagebox.showerror("错误", "请选择文件")
            return
        with shelve.open(shelf_file) as s:
            self._process_val.set(s['Process_Val'])
            self._test_id.set(s['Test_ID'])
            self._temp_val.set(s['Temp_val'])
            self._tank_id1.set(s['Tank_ID1'])
            self._tank_id2.set(s['Tank_ID2'])
            self._tank_id3.set(s['Tank_ID3'])
            self._tank_id4.set(s['Tank_ID4'])
            self._holding_time.set(s['Holding_time'])

            pressure = s['Pressure']
            self._add_figure_text(0, 0.9, 'Process_Val: ' + str(s['Process_Val']))
            self._add_figure_text(0, 0.8, 'Test_ID: ' + str(s['Test_ID']))
            self._add_figure_text(0, 0.7, 'Temp_val: ' + str(s['Temp_val']))
            self._add_figure_text(0, 0.6, 'Tank_ID1: ' + str(s['Tank_ID1']))
            self._add_figure_text(0, 0.5, 'Tank_ID2: ' + str(s['Tank_ID2']))
            self._add_figure_text(0, 0.4, 'Tank_ID3: ' + str(s['Tank_ID3']))
            self._add_figure_text(0, 0.3, 'Tank_ID4: ' + str(s['Tank_ID4']))
            self._add_figure_text(0, 0.2, 'Holding_time: ' + str(s['Holding_time']))
            self._add_figure_text(0, 0.1, 'Time: ' + s['Time'])

        self.ax.clear()
        self.ax.plot(pressure)
        self.fig.canvas.draw_idle()
        messagebox.showinfo('信息', '读取成功！')

    @logger.catch
    def _on_write_click(self):
        """写入文件按钮回调"""
        if (self._tank_id1.get() == '' or self._tank_id2.get() == ''
                or self._tank_id3.get() == '' or self._tank_id4.get() == ''):
            messagebox.showerror("错误", "请输入完整信息")
            return
        self._generate_folder()
        with shelve.open(self._shelf_file) as s:
            s['Pressure'] = self._y_data
            s['Time'] = time.strftime("%Y-%m-%d %H:%M:%S", self._current_time)
            s['Process_Val'] = self._process_val.get()
            s['Test_ID'] = str(self._test_id.get())
            s['Temp_val'] = self._temp_val.get()
            s['Tank_ID1'] = self._tank_id1.get()
            s['Tank_ID2'] = self._tank_id2.get()
            s['Tank_ID3'] = self._tank_id3.get()
            s['Tank_ID4'] = self._tank_id4.get()
            s['Holding_time'] = self._holding_time.get()
            self._add_figure_text(0, 0.9, 'Process_Val: ' + str(self._process_val.get()))
            self._add_figure_text(0, 0.8, 'Test_ID: ' + self._test_id.get())
            self._add_figure_text(0, 0.7, 'Temp_val: ' + str(self._temp_val.get()))
            self._add_figure_text(0, 0.6, 'Tank_ID1: ' + self._tank_id1.get())
            self._add_figure_text(0, 0.5, 'Tank_ID2: ' + self._tank_id2.get())
            self._add_figure_text(0, 0.4, 'Tank_ID3: ' + self._tank_id3.get())
            self._add_figure_text(0, 0.3, 'Tank_ID4: ' + self._tank_id4.get())
            self._add_figure_text(0, 0.2, 'Holding_time: ' + str(self._holding_time.get()))
            self._add_figure_text(0, 0.1, 'Time: ' + time.strftime("%Y-%m-%d %H:%M:%S", self._current_time))
        logger.info(self._shelf_file)
        logger.info(self._folder_name)
        messagebox.showinfo('信息', '写入成功！')

    @logger.catch
    def _get_pressure(self):
        """获取传感器压力读数"""
        return self.read_modbus_rtu()

    def _generate_folder(self):
        """生成数据保存文件夹"""
        try:
            self._folder_name = filedialog.askdirectory() + "/" + time.strftime("%Y%m%d_",
                                                                                self._start_time) + self._test_id.get()
            if not os.path.exists(self._folder_name):
                os.mkdir(self._folder_name)
            self._shelf_file = os.path.join(self._folder_name, 'shelf')
        except Exception as e:
            raise Exception(f"文件夹生成失败: {e}")

    @logger.catch
    def _on_record_click(self):
        """开始/停止记录按钮回调"""
        if self._is_recording:
            self._is_recording = False
            self._record_ctrl_var.set("开始记录")
        else:
            try:
                if self._test_id.get() == '':
                    messagebox.showerror("错误", "请输入记录编号")
                    return
                self.connect(self._cmb_port.get(), 9600, 1, "N", 8)
                self._is_recording = True
                self._record_ctrl_var.set("停止记录")
                self._start_data_thread()
                messagebox.showinfo('信息', '启动成功！')
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", "启动失败")

    def _on_relief_valve_click(self):
        """泄压阀按钮回调"""
        self._toggle_button(self._btn_relief_valve, self._relief_valve_var, 0)

    def _on_high_pressure_click(self):
        """高压泵按钮回调"""
        self._toggle_button(self._btn_high_pressure, self._high_pressure_var, 1)

    def _on_pressure_water_click(self):
        """高压进水按钮回调"""
        self._toggle_button(self._btn_pressure_water, self._pressure_water_var, 2)

    def _on_save_click(self):
        """保存图片按钮回调"""
        filename = filedialog.asksaveasfilename(defaultextension=".png")
        if filename:
            self.fig.savefig(filename)

    def _toggle_button(self, btn, btn_var, index):
        """切换按钮的开关状态"""
        if self._valve_states[index]:
            btn['bg'] = 'green'
            self._valve_states[index] = False
            btn_var.set("打开")
        else:
            btn['bg'] = 'red'
            self._valve_states[index] = True
            btn_var.set("关闭")

    def _on_closing(self):
        """窗口关闭回调：安全停止线程后销毁窗口"""
        self._is_recording = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.destroy()


def main():
    """主函数"""
    app = PressureTestApp()
    app.mainloop()


if __name__ == '__main__':
    main()
