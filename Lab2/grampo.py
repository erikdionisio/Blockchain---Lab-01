import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print("🎧 Grampo Global ativado. A escutar TODA a rede sisdef...")
    # O '#' significa "inscrever em todos os subtópicos existentes a partir daqui"
    client.subscribe("sisdef/#") 

def on_message(client, userdata, msg):
    print(f"[{msg.topic}] => {msg.payload.decode('utf-8', errors='ignore')}")

client = mqtt.Client(client_id="escuta_fantasma_007")
client.on_connect = on_connect
client.on_message = on_message

client.connect("broker.hivemq.com", 1883, 60)
client.loop_forever()