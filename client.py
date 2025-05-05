# client.py
import socket
import time

# 建立 UDP Socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

username = input("請輸入你的名字：")
server_ip = input("請輸入Server IP地址：")
server_address = (server_ip, 12345)

# 發送使用者名稱給Server
client_socket.sendto(f"USERNAME:{username}".encode(), server_address)

# 等待Server回覆
data, _ = client_socket.recvfrom(1024)
message = data.decode()

if message.startswith("START"):
    print("開始遊戲！")
    start_time = time.time()
    attempts = 0

    while True:
        guess = input("請輸入你的猜測：")
        client_socket.sendto(f"GUESS:{guess}".encode(), server_address)
        
        data, _ = client_socket.recvfrom(1024)
        result = data.decode()
        print(f"回覆：{result}")
        
        if result.startswith("WIN:"):
            print(result[4:])  # 秀出WIN後面的訊息
            break
        
        attempts += 1

# 結束後詢問是否再玩一次（這裡可以自己加功能）

client_socket.close()
