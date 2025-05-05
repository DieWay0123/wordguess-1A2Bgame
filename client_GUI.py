import tkinter as tk
import socket
import threading
from datetime import datetime

class ClientGUI:
    def __init__(self, root):
        # socket相關參數
        self.socket = None
        self.sever_address = None
        self.client_address = ('127.0.0.1', 12345)
        self.receive_thread = None

        # 猜數字相關參數
        self.ready_to_guess = None
        self.answer_length = 0
        self.username = None
        self.guess_count = 0
        self.start_time = None
        
        self.root = root
        self.root.title("UDP猜字串-Client")
        self.root.geometry("500x500")


        # === 輸入連線相關資訊部分GUI ===
        self.input_entry_frame = tk.Frame(self.root)
        tk.Label(self.input_entry_frame, text="使用者名稱: ").pack()
        self.name_entry = tk.Entry(self.input_entry_frame)
        self.name_entry.pack()
        
        tk.Label(self.input_entry_frame, text="Server IP: ").pack()
        self.ip_entry = tk.Entry(self.input_entry_frame)
        self.ip_entry.pack()

        tk.Label(self.input_entry_frame, text="伺服器 Port: ").pack()
        self.port_entry = tk.Entry(self.input_entry_frame)
        self.port_entry.pack()
        
        self.start_button = tk.Button(self.input_entry_frame, text="連線並開始遊戲", command=self.start_game)
        self.start_button.pack(pady=5)
        
        
        # === 輸出訊息監控窗部分GUI ===
        self.output_text_frame = tk.Frame(self.root)
        self.output_text = tk.Text(self.output_text_frame)
        self.output_text.pack()
        
        
        # === 輸入猜測部分GUI ===
        self.guess_frame = tk.Frame(self.root)
        tk.Label(self.guess_frame, text="輸入猜測字串: ").pack()
        self.guess_entry = tk.Entry(self.guess_frame)
        self.guess_entry.pack()
        
        self.guess_button = tk.Button(self.guess_frame, text="送出猜測", command=self.send_guess, state='disabled')
        self.guess_button.pack(pady=5)
        
        # === GUI grid排版調整
        self.input_entry_frame.grid(row=0, column=0)
        self.output_text_frame.grid(row=1, column=0)
        self.guess_frame.grid(row=2, column=0)
    
    def start_game(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()
        username = self.name_entry.get()
        
        if not ip or not port or not username:
            self.modify_output_text("[Error]: 請填寫完整IP、Port和username\n")
            return
        
        try:
            port = int(port)
        except ValueError:
            self.modify_output_text("[Error]: 請確認填寫之port為整數數字")
            return

        self.server_address = (ip, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(self.client_address)
        self.modify_output_text(f"[Success]: 已連線到伺服器{ip}:{port}\n")
        
        # 告訴server client的地址
        self.socket.sendto(f"[Connecting]: client->{ip}:{port}".encode(), self.server_address)
        self.guess_count = 0
        self.username = username
        self.receive_thread = threading.Thread(target=self.receive_response, daemon=True)
        self.receive_thread.start()
    
    def send_guess(self):
        guess = self.guess_entry.get().strip().upper()

        # 若目前server還未設定好答案就送出猜測，則跳出等待訊息        
        if not self.ready_to_guess:
            self.modify_output_text("[Waiting...]: 等待接收數字的個數(N個數字/文字)\n")
            return
        
        # 驗證猜測輸入部分
        if any(c not in "0123456789ABCDEF" for c in guess):
            self.modify_output_text("[Error]: 請只輸入0-0或A-F的字元\n")
            return
        if len(set(guess)) != len(guess):
            self.modify_output_text("[Error]: 請確認輸入字元皆不重複\n")
            return
        if self.answer_length != 0 and len(guess) != self.answer_length:
            self.modify_output_text(f"[Error]: 請確認輸入長度為{self.answer_length}\n")
            return
        
        # 驗證輸入正確後，開始處理向server送出猜字串的udp封包部分
        self.guess_count += 1
        try:
            self.socket.sendto(f"[Guess]: {guess}".encode(), self.server_address)
            self.modify_output_text(f"[Info]: {self.server_address}已送出猜測({guess})\n")
        except Exception as e:
            self.modify_output_text(f"[Error]: >{self.server_address[0]}:{self.server_address[1]}，傳送猜字串封包失敗失敗({e})\n")
    
    def receive_response(self):
        while True:
            try:
                data, _ = self.socket.recvfrom(1024)
                response = data.decode()
                
                # 檢查有無收到server送來的答案已設定好之Ready封包，接下來才可開始猜字串
                if response.startswith("[Ready]:"):
                    self.ready_to_guess = True # 設定遊戲已開始，方便後續遊戲狀態判斷
                    if "[Ready]:" in response:
                        self.answer_length = int(response.split(":")[1].split("，")[0]) # 從server發送的ready訊息得到答案n為多少
                    self.modify_output_text("[Info]: Server已設定好答案，請輸入你猜的字串(0~9, A~F)\n")
                    self.guess_button.config(state='normal') # 設定猜答案按鈕可以開始用，在設定好答案前為不可用
                    self.start_time = datetime.now() # 設定開始猜的時間
                    continue            
                elif response.startswith("[Success]:") and "恭喜猜對" in response:
                    duration = (datetime.now() - self.start_time).total_seconds()
                    finish_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.modify_output_text(f"[Game Finish!]: 共猜{self.guess_count}次，用時{duration:.2f}秒\n")
                    self.guess_button.config(state="disabled")
                    # 傳送使用者遊戲資訊回server
                    userinfo_msg = f"[USERINFO]:{self.username},{self.guess_count},{duration},{finish_time_str}"
                    self.socket.sendto(userinfo_msg.encode(), self.server_address)
            except Exception as e:
                self.modify_output_text(f"[Error]: {e}")
                break
            self.modify_output_text(f"[Server Reply]: {response}\n")

    
    def modify_output_text(self, text):
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text)
        self.output_text.config(state="disabled")
        self.output_text.see(tk.END)

# 啟動 Client GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ClientGUI(root)
    root.mainloop()