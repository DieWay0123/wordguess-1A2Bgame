import tkinter as tk
import socket
import threading
from datetime import datetime

class ClientGUI:
    def __init__(self, root):
        # socket相關參數
        self.socket = None
        self.server_address = None
        self.client_address = ('192.168.16.99', 12345)
        self.receive_thread = None

        # 猜數字相關參數
        self.ready_to_guess = None
        self.answer_length = 0
        self.username = None
        self.guess_count = 0
        self.start_time = None
        
        # timer相關參數
        self.timeout_timer = None # 用以存放timer thread
        self.TIMEOUT_DURATION = 120 # 設定多久沒有動作會timeout(單位秒)
        self.game_running = False
        
        # Tkinter相關參數
        self.root = root
        self.root.title("UDP猜字串-Client")
        self.root.minsize(900, 540)


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
        self.text_frame = tk.Frame(self.root)
        self.text_frame.rowconfigure(0, weight=1)
        self.text_frame.columnconfigure(0, weight=1)
        # 用於監控的訊息輸出框
        self.output_text = tk.Text(self.text_frame, state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.tag_config("bold", font=("Helvetica", 10, "bold"))
        self.output_text.tag_config("error", foreground="red")
        self.output_text.tag_config("success", foreground="green")
        self.output_text.tag_config("info", foreground="blue", font=("Helvetica", 10, "bold"))
        # 加上scrollbar，可以調整訊息框閱讀範圍
        scrollbar_x = tk.Scrollbar(self.text_frame, orient="horizontal", command=self.output_text.xview)
        scrollbar_y = tk.Scrollbar(self.text_frame, orient='vertical', command=self.output_text.yview)
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        
        # === 輸入猜測部分GUI ===
        self.guess_frame = tk.Frame(self.root)
        tk.Label(self.guess_frame, text="輸入猜測字串: ").pack()
        self.guess_entry = tk.Entry(self.guess_frame)
        self.guess_entry.pack()
        
        self.guess_button = tk.Button(self.guess_frame, text="送出猜測", command=self.send_guess, state='disabled')
        self.guess_button.pack(pady=5)
        # replay按鈕
        self.replay_button = tk.Button(self.guess_frame, text="再玩一次", command=self.replay_game, state="disabled")
        self.replay_button.pack()
        # 結束遊戲按鈕
        self.quit_button = tk.Button(root, text="結束遊戲", command=self.quit_game)
        self.quit_button.pack()

        # === GUI grid排版調整
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.input_entry_frame.grid(row=0, column=0)
        self.text_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.guess_frame.grid(row=2, column=0)

    def quit_game(self):
        try:
            quit_message = "QUIT"
            self.socket.sendto(quit_message.encode(), self.server_address)
        except Exception as e:
            print(f"Error sending quit message: {e}")
        finally:
            self.socket.close()
            self.root.destroy()  # 關閉 Tkinter GUI


    def replay_game(self):
        self.reset_timeout_timer()
        if self.socket:
            self.socket.sendto(f"[Replay]:{self.client_address}".encode(), self.server_address)
            self.replay_button.config(state="disabled")
            self.guess_entry.delete(0, tk.END)
            self.modify_output_text("[Replay Requesting]已請求重新開始，請稍候Server設定新答案...\n", "info")

    def test_server_connection(self, server_address):
        ip = server_address[0]
        port = server_address[1]
        try:
            self.modify_output_text(f"[Info]: 正在確認連線{self.client_address[0]}:{self.client_address[1]}->{ip}:{port}")
            self.socket.sendto(f"[Connecting]: client->{ip}:{port}".encode(), self.server_address)
            data, addr = self.socket.recvfrom(1024)
            self.modify_output_text(f"[Connection Success!]: 伺服器回應為: {data.decode()}\n", "success")
            return True
        except socket.timeout:
            return False
        except Exception as e:
            self.modify_output_text(f"[Error]: {e}\n", "error")
            return False
        finally:
            self.socket.settimeout(None)

    def start_game(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()
        username = self.name_entry.get()
        
        if not ip or not port or not username:
            self.modify_output_text("[Error]: 請填寫完整IP、Port和username\n", "error")
            return
        
        try:
            port = int(port)
        except ValueError:
            self.modify_output_text("[Error]: 請確認填寫之port為整數數字\n", "error")
            return

        self.server_address = (ip, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        self.socket.bind(self.client_address)
        self.socket.settimeout(10)
        
        # ================= 確認server啟動 =======================
        if not self.test_server_connection(self.server_address):
            self.modify_output_text("[Error]: 連線失敗，無法連線到伺服器，請確認伺服器是否已啟動\n", "error")
            self.socket.close()
            return
        
        # =======================================================

        self.modify_output_text(f"[Success]: 已連線到伺服器{ip}:{port}，等待server設定答案...\n", "success")
        self.game_running = True
        # 告訴server client的地址
        self.guess_count = 0
        self.username = username
        self.start_button.config(state="disabled")
        self.receive_thread = threading.Thread(target=self.receive_response, daemon=True)
        self.receive_thread.start()
        self.reset_timeout_timer()
    
    def send_guess(self):
        guess = self.guess_entry.get().strip().upper()
        self.reset_timeout_timer()

        # 若目前server還未設定好答案就送出猜測，則跳出等待訊息        
        if not self.ready_to_guess:
            self.modify_output_text("[Waiting...]: 等待接收數字的個數(N個數字/文字)\n")
            return
        
        # 驗證猜測輸入部分
        if any(c not in "0123456789ABCDEF" for c in guess):
            self.modify_output_text("[Error]: 請只輸入0-0或A-F的字元\n", "error")
            return
        if len(set(guess)) != len(guess):
            self.modify_output_text("[Error]: 請確認輸入字元皆不重複\n", "error")
            return
        if self.answer_length != 0 and len(guess) != self.answer_length:
            self.modify_output_text(f"[Error]: 請確認輸入長度為{self.answer_length}\n", "error")
            return
        
        # 驗證輸入正確後，開始處理向server送出猜字串的udp封包部分
        self.guess_count += 1
        try:
            self.socket.sendto(f"[Guess]: {guess}".encode(), self.server_address)
            self.modify_output_text(f"[Info]: {self.server_address}已送出猜測({guess})\n", "info")
        except Exception as e:
            self.modify_output_text(f"[Error]: >{self.server_address[0]}:{self.server_address[1]}，傳送猜字串封包失敗失敗({e})\n", "error")
    
    def receive_response(self):
        while self.game_running:
            try:
                if self.socket:
                    data, _ = self.socket.recvfrom(1024)
                response = data.decode()
                self.reset_timeout_timer()
                
                # 檢查有無收到server送來的答案已設定好之Ready封包，接下來才可開始猜字串
                if response.startswith("[Ready]:"):
                    self.ready_to_guess = True # 設定遊戲已開始，方便後續遊戲狀態判斷
                    if "[Ready]:" in response:
                        self.answer_length = int(response.split(":")[1].split("，")[0]) # 從server發送的ready訊息得到答案n為多少
                    self.modify_output_text(f"[Info]: Server已設定好答案(本次長度:{self.answer_length})，請輸入你要猜的字串(0~9, A~F)\n", "info")
                    self.guess_button.config(state='normal') # 設定猜答案按鈕可以開始用，在設定好答案前為不可用
                    self.start_time = datetime.now() # 設定開始猜的時間
                    self.guess_count = 0
                    continue
                elif response.startswith("[Guess Reply]:") and "恭喜猜對" in response:
                    self.replay_button.config(state="normal") # 設定reaply按鈕猜對後可以再次遊玩
                    duration = (datetime.now() - self.start_time).total_seconds()
                    finish_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.modify_output_text(f"[Game Finish!]: 共猜{self.guess_count}次，用時{duration:.2f}秒\n", "bold")
                    self.modify_output_text(f"若要再次遊玩請點擊下方「再玩一次」按鈕!\n", "success")
                    self.guess_button.config(state="disabled")
                    self.start_button.config(state="normal")
                    # 傳送使用者遊戲資訊回server
                    userinfo_msg = f"[USERINFO]->{self.username},{self.guess_count},{duration},{finish_time_str}"
                    self.socket.sendto(userinfo_msg.encode(), self.server_address)
                elif response.startswith("[Guess Reply]"):
                    self.modify_output_text(f"{response}\n", 'bold')
                elif response.startswith("[Congratulations!]:"):
                    self.modify_output_text(f"{response.split(":")[1]}\n", 'bold')
                elif response.startswith("[Timeout]:"):
                    self.modify_output_text(f"{response}", "error")
                    self.guess_button.config(state="disabled")
                    self.replay_button.config(state="disabled")
                    self.game_running = False
                    self.start_button.config(state="normal")
                    self.modify_output_text(f"[Info]: 客戶端socket已關閉\n", "info")
                    self.socket.close()
            except OSError:
                break
            except Exception as e:
                # self.modify_output_text(f"[Error]: {e}\n", "error")
                continue
            # self.modify_output_text(f"[Server Reply]: {response}\n")
    
    def modify_output_text(self, text, tag=None):
        self.output_text.config(state="normal")
        if tag:
            self.output_text.insert(tk.END, text, tag)
        else:
            self.output_text.insert(tk.END, text)
        self.output_text.config(state="disabled")
        self.output_text.see(tk.END)

    # 當有動作時，重製timeout timer
    def reset_timeout_timer(self):
        # 由於是threading，需要先把舊的thread給取消掉再開新的timer
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(self.TIMEOUT_DURATION, self.handle_timeout)
        self.timeout_timer.start()
        
    def handle_timeout(self):
        self.modify_output_text(f"[Timeout]: {self.TIMEOUT_DURATION}秒內沒有互動，遊戲已自動結束!\n", "error")
        self.game_running = False
        print(self.server_address)
        # 同時也中斷server socket的監聽
        try:
            self.socket.sendto("[Timeout]: Client已閒置過久，自動中止遊戲".encode(), self.server_address)
        except Exception as e:
            self.modify_output_text(f"[Error]: 傳送timeout通知給server失敗: {e}\n", "error")
        # 關閉socket並解除綁定
        if self.socket:
            try:
                self.socket.close()
                self.modify_output_text("[Info]: 客戶端socket已關閉\n", "info")
            except Exception as e:
                self.modify_output_text(f"[Error]: 關閉socket時發生錯誤：{e}\n", "error")
            finally:
                self.socket = None
        # 重製各個參數
        self.game_running = False
        self.answer_length = 0
        self.guess_count = 0
        self.server_address = None
        # 調整按鈕設定
        self.start_button.config(state="normal")
        self.guess_button.config(state="disabled")
        self.replay_button.config(state="disabled")            

# 啟動 Client GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ClientGUI(root)
    root.mainloop()