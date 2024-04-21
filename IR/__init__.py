from lib import keyboard, st7789py, mhconfig, mhoverlay
from machine import Pin, PWM, SPI, soft_reset, SDCard
from time import sleep
import uos

# trying to import libraries
try:
    from UpyIrTx import UpyIrTx
    from UpyIrRx import UpyIrRx
except:
    try:
        from apps.IR.UpyIrTx import UpyIrTx
        from apps.IR.UpyIrRx import UpyIrRx
    except:
        try:
            from sd.apps.IR.UpyIrTx import UpyIrTx
            from sd.apps.IR.UpyIrRx import UpyIrRx
        except:
            print("Could not import libraries")

# os.path.isdir() doesn't work, so using this
def is_dir(dir_path):
    try:
        uos.chdir(dir_path)
        return True
    except:
        return False

# reads signals from .ir to json
def load_ir_signals(filename):
    ir_signals = {}
    with open(filename, 'r') as file:
        current_signal = None
        for line in file:
            if line.startswith('name:'):
                current_signal = {'name': line.split(':')[1].strip(), 'data': None}
            elif line.startswith('data:'):
                current_signal['data'] = [int(x) for x in line.split(':')[1].strip().split()]
                ir_signals[current_signal['name']] = current_signal
                del current_signal
    file.close()
    return ir_signals
   
#saving
def save_scanned_signal(filename, signal_name, data):
    with open(f"/sd/ir/scanned/{filename}.ir", 'a')as file:
        data_str = ' '.join(map(str, data))
        try:
            temp = file.tell()
        except:
            temp = 0
        if temp == 0:
            file.write("Filetype: IR signals file\nVersion: 1\n# Generated by Cardputer IR app")
        del temp
        file.write(f"\n#\nname: {signal_name}\ntype: raw\nfrequency: 38200\nduty_cycle: 0.330000\ndata: {data_str}")

try:
    # mount SD, init hardware and variables
    sd = SDCard(slot=2, sck=Pin(40), miso=Pin(39), mosi=Pin(14), cs=Pin(12))
    uos.mount(sd, '/sd')
    spi = SPI(1, baudrate=40000000, sck=Pin(36), mosi=Pin(35), miso=None)
    tft = st7789py.ST7789(
        spi,
        135,
        240,
        reset=Pin(33, Pin.OUT),
        cs=Pin(37, Pin.OUT),
        dc=Pin(34, Pin.OUT),
        backlight=Pin(38, Pin.OUT),
        rotation=1,
        color_order=st7789py.BGR
    )
    kb = keyboard.KeyBoard()
    config = mhconfig.Config()
    overlay = mhoverlay.UI_Overlay(config=config, keyboard=kb, display_py=tft)
    PIN_IR_LED = 44
    ir_led = Pin(PIN_IR_LED, Pin.OUT)
    tx = UpyIrTx(0, PIN_IR_LED)
    led_status = 0
    directory_path = "/sd/ir"
    if not is_dir(directory_path):
        uos.mkdir(directory_path)

    while True:  # main loop
        # main menu
        user_choice = overlay.popup_options(["Load file", "Scan remote", "IR On", "IR Off", "Exit"], title=f"IR state: {led_status}", shadow=True, extended_border=True)

        if user_choice == "Load file":
            selected_path = overlay.popup_options(uos.listdir(directory_path))  # ls
            if selected_path is None: #  if user presses ESC, return to previous dir
                directory_path = "/".join(list(dir_path.split('/')[0:-1]))
            elif is_dir(f"{directory_path}/{selected_path}"):  # if user tries to open a directory, enter it
                directory_path = directory_path + '/' + selected_path
            elif selected_path.endswith('.ir'):
                loaded_ir_signals = load_ir_signals(f"{directory_path}/{selected_path}")  # loads signals
                while True:
                    sig_name = overlay.popup_options_2d(sorted(loaded_ir_signals), extended_border=True, scrollable=True)  # asks user which signal to send
                    if sig_name is None: # if user presses ESC, exit to main menu
                        break
                    
                    signal = loaded_ir_signals.get(sig_name)  # find a data from a signal and send it
                    if signal:
                        tx.send_raw(signal['data'])
                del loaded_ir_signals, sig_name  # cleanup

            else:
                overlay.popup("Only .ir can be opened here")

        elif user_choice == "Scan remote":
            overlay.popup("Connent IR reciever module to groove. Press enter when ready")
            IR_RX_PIN = overlay.popup_options(['1', '2'], title="Select pin", extended_border=True)
            rx = UpyIrRx(Pin(int(IR_RX_PIN), Pin.IN))
            scan_filename = overlay.text_entry(title="Filename to write", blackout_bg=True)
            
            while True:
                overlay.draw_textbox("Scanning, press BtnRst to exit", 120, 62, padding=8, shadow=True, extended_border=True)
                rx.record(wait_ms=2000)  # listens at IR_RX_PIN for signals
                if rx.get_mode() == UpyIrRx.MODE_DONE_OK:
                    scan_name = overlay.text_entry(title="Enter signal name", blackout_bg=True)
                    if scan_name == '':  # exit to main menu if empty name
                        break
                    signal_list = rx.get_record_list()  # get data of signal
                    save_scanned_signal(scan_filename, scan_name, signal_list)
            
            del rx, IR_RX_PIN, scan_filename, scan_name, signal_list  # cleanup
                
        elif user_choice == "IR On":
            led_status = 1
        elif user_choice == "IR Off":
            led_status = 0
        elif user_choice == "Exit":
            ir_led.value(0)
            soft_reset()

        ir_led.value(led_status)
        sleep(0.1)

except Exception as e:  # for debugging
    overlay.popup(str(e))
    print(e)
    soft_reset()
