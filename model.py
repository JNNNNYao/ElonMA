import os
import io
import sys
import time
from PIL import Image

import pika

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='bot2model')
    channel.queue_declare(queue='model2bot')

    def callback(ch, method, properties, body):
        Payload = body.decode("utf-8")
        assert type(Payload) == str
        assert '+++' in Payload
        channel_id, url = Payload.split('+++')
        print(channel_id)
        print(url)

        # TODO: get image & call model forward pass
        time.sleep(5)   # simulate model inference time
        img = Image.open('test.jpeg')   # assume having PIL image
                                        # Image.fromarray(numpy_image)

        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_byte_data = str(img_buffer.read())
        data = channel_id + '+++' + img_byte_data
        channel.basic_publish(exchange='', routing_key='model2bot', body=data)

    channel.basic_consume(queue='bot2model', on_message_callback=callback, auto_ack=True)
    print('[model] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)