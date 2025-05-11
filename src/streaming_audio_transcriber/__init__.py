import streamlit as st
import websockets
import base64
import json
import pyaudio
import asyncio
import os

from dotenv import load_dotenv

load_dotenv(".env")

import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        os.getenv("COLLECTION_BROADCAST_RABBITMQ_HOST"),
        os.getenv("COLLECTION_BROADCAST_RABBITMQ_PORT"),
        "/",
        pika.PlainCredentials(
            username=os.getenv("COLLECTION_BROADCAST_RABBITMQ_USER"),
            password=os.getenv("COLLECTION_BROADCAST_RABBITMQ_PASSWORD"),
        ),
    )
)
channel = connection.channel()

queueName = os.getenv("RABBITMQ_QUEUE_NAME")
channel.queue_declare(queue=queueName)

if "text" not in st.session_state:
    st.session_state["text"] = "transcribing..."
    st.session_state["run"] = False

FRAMES_PER_BUFFER = 3200
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
p = pyaudio.PyAudio()

# starts recording
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER,
    input_device_index=2,
)


def start_transcribing():
    st.session_state["run"] = True


def stop_transcribing():
    st.session_state["run"] = False


st.title("Get real-time transcription")

start, stop = st.columns(2)
start.button("Start transcribing", on_click=start_transcribing)

stop.button("Stop transcribing", on_click=stop_transcribing)

URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"


async def send_receive():
    print(f"Connecting websocket to url ${URL}")

    async with websockets.connect(
        URL,
        extra_headers=(("Authorization", os.getenv("ASSEMBLY_AI_API_KEY")),),
        ping_interval=5,
        ping_timeout=20,
    ) as _ws:

        r = await asyncio.sleep(0.1)
        print("Receiving Session Begins ...")

        session_begins = await _ws.recv()
        print(session_begins)
        print("Sending messages ...")

        async def send():
            print("in send")
            while st.session_state["run"]:
                try:
                    data = stream.read(FRAMES_PER_BUFFER)
                    data = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"audio_data": str(data)})
                    r = await _ws.send(json_data)

                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break

                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

                r = await asyncio.sleep(0.01)

        async def receive():
            print("in receive")
            while st.session_state["run"]:
                try:
                    result_str = await _ws.recv()
                    result = json.loads(result_str)["text"]

                    if json.loads(result_str)["message_type"] == "FinalTranscript":
                        channel.basic_publish(
                            exchange="",
                            routing_key=queueName,
                            body=result,
                        )
                        print(f" [x] Sent ${result}")
                        st.session_state["text"] = result
                        st.markdown(st.session_state["text"])

                except websockets.exceptions.ConnectionClosedError as e:
                    print(e)
                    assert e.code == 4008
                    break

                except Exception as e:
                    print(e)
                    assert False, "Not a websocket 4008 error"

        send_result, receive_result = await asyncio.gather(send(), receive())


asyncio.run(send_receive())
