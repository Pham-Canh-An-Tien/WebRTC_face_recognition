
## Tien Pham
## 1001909301

import argparse
import asyncio
import json
import logging
import threading
import os
import platform
import ssl
import time
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from faceregtrack import FacialRecognitionTrack
from facerec_core.mtcnn_detect import MTCNNDetect
from facerec_core.tf_graph import FaceRecGraph
from clienthandler import Client, ClientManager
from facerec_core.face_feature import FaceFeature
from datasetmanager import FaceDataManager
ROOT = os.path.dirname(__file__)
routes = web.RouteTableDef()
_id = 0

# Create the web application
app = web.Application()
def create_new_client(pc):
    global clients, _id
    clients[_id] = Client(pc, _id)
    _id+=1;
    return _id - 1;

async def remove_client(_id):
    if _id in clients:
        await clients[_id].close()
        del clients[_id]

## Main request to the home page
@routes.get("/")
async def index(request):
    content = open(os.path.join(ROOT, "frontend/client.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

## Call the main function from main.js
@routes.get("/js/main.js")
async def main_js(request):
    content = open(os.path.join(ROOT, "frontend/js/main.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

@routes.get("/js/video_stream.js")
async def video_stream_js(request):
    content = open(os.path.join(ROOT, "frontend/js/video_stream.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

@routes.get("/js/sample.js")
async def sample_js(request):
    content = open(os.path.join(ROOT, "frontend/js/sample.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


def recog_worker(client, data):
    while data[0]:
        client.generate_trackers_face_features()


@routes.post("/offer")
async def offer(request):
    params = await request.json()
    print(params);
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    client_id = client_manager.create_new_client(pc)


    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await client_manager.remove_client(client_id) #this already handles pc closing

    faceregtrack = FacialRecognitionTrack(face_detect, client_manager.get_client(client_id));

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            client = client_manager.get_client(client_id)
            if "$register$" in message: #this is some poorman message handling :)
                new_subject = message.split("$register$")[1]
                print("Registering for subject: "+new_subject)
                client.toggle_register_mode(new_subject)
                channel.send("$register$") #ack back
            elif "$recognize$" in message:
                print("Turned on recognition mode")
                client.toggle_recognition_mode()
                channel.send("$recognize$") #ack back


    @pc.on("close")
    async def on_close(track):
        print("Connection with client: "+str(client_id)+" closed")
        #data[0] = False
        #recog_worker_thread.join()
        await client_manager.remove_client(client_id)

    @pc.on("track")
    def on_track(track):
        print("Track %s received" % track.kind)
        if track.kind == "video":
            faceregtrack.update(track);
            


    await pc.setRemoteDescription(offer)

    for t in pc.getTransceivers():
        if t.kind == "video":
            pc.addTrack(faceregtrack)


    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("Connection with client formed")
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )





async def on_shutdown(app):
    await client_manager.on_shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web RTC Face Recognition")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    app.on_shutdown.append(on_shutdown)
    app.add_routes(routes)
    MTCNNGraph = FaceRecGraph()
    FaceGraph = FaceRecGraph()

    ## Using MTCNN for face detection
    face_detect = MTCNNDetect(MTCNNGraph, scale_factor=2) 
    face_recog = FaceFeature(FaceGraph)
    dataset = FaceDataManager()
    client_manager = ClientManager(dataset, face_recog)

    ## Run the web app at port 8080
    web.run_app(app, port=args.port, ssl_context=ssl_context)
