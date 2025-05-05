import socket
import time

SERVER_IP = "#.#.#.#"
SERVER_PORT = 12345

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # 使用ipv4+udp協議
server_socket.bind(('192.168.131.83', 12345)) # 設定server端監聽的IP和port

print(socket.gethostname())
print("建立UDP Socket(UDP猜字串小遊戲 啟動中)")

allowed_chars = set("0123456789ABCDEF")
def input_is_valid(answer: str, answer_length: int):
    if len(answer) != answer_length:
        return False
    if any(allowed_chars for c in answer):
        return False
    return True
# 輸入N個數字的數字/英文
answer_length = int(input(f"Step1: {SERVER_IP}>> 請輸入位數N: "))
while True:
    answer = input(f"Step 2: Server {SERVER_IP} >>N位數的正確字串: (N個數字/文字的字串，數字不重複。輸入0結束程式。可用數字/文字為：{text})")
    if input_is_valid(answer):
        break
    else:
        print("請再次檢查輸入位數和是否為可用數字/文字，請重新輸入！")

players = []



while True:
    data, addr = server_socket.recvfrom(1024) # 接收1024bytes資料
    message = data.decode()
    ttl = time.time()

    if message.startswith("USERNAME:"):
        username = message.split(":")[1]
        print(F"[!通知] 玩家 {username} 從 {addr} 加入遊戲")
        message = "START: 開始猜數字遊戲，請輸入N個數字/文字"
        server_socket.sendto(message.encode(), addr)
        
        start_time = time.time()
        guess_attempts = 0
        
        while True:
            guess_data, _ = server_socket.recvfrom(1024)
            guess_message = guess_data.decode()

            if guess_message.startswith("GUESS:"):
                guess = guess_message.split(":")[1]
                guess_attempts += 1

                guess_A = 0
                guess_B = 0
                for i in range(len(answer)):
                    if guess[i]==answer[i]:
                        guess_A += 1
                    elif guess[i] in answer:
                        guess_B += 1
                guess_result = f"{guess_A}A{guess_B}B"
                server_socket.sendto(guess_result.encode(), addr)

                if guess_A == answer_length:
                    finish_time = time.time() - start_time
                    player_record = (username, finish_time, guess_attempts)
                    players.append(player_record)
                    players.sort(key=lambda x: x[1])

                    rank = players.index(player_record)+1
                    msg = f"WIN:恭喜！你是第{rank}名，總共猜了{guess_attempts}次，花了{finish_time:.2f}秒"
                    server_socket.sendto(msg.encode(), addr)
                    break  # 玩家猜對，退出這個while
    else:
        if ttl - time.time() >= 30000:
            break
        server_socket.sendto(b"wrong format", addr)


server_socket.close()