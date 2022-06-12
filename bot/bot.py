import os
import io
import ast
import json
import requests
from threading import Thread

import pika
import tweepy
import discord
from discord.ext import tasks

bot_token = os.environ['bot_token']
# docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' container_name_or_id
rabbitmq_ip = os.environ['rabbitmq_ip']
bearer_token = os.environ['bearer_token']

crawler = tweepy.Client(bearer_token)
user_id = 44196397  # @elonmusk
user_id_demo = 1362728065864884224
# user_id = 1367531   # @FoxNews, testing
tweet_url = 'https://twitter.com/elonmusk/status/'
tweet_url_demo = 'https://twitter.com/william36253736/status/'
# tweet_url = 'https://twitter.com/FoxNews/status/'   # testing

# Defining Binance API URL
key = "https://api.binance.com/api/v3/ticker/price?symbol="
currencies = "DOGEUSDT"

class Bot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.most_recent_tweet_id = None
        self.most_recent_tweet_id_demo = None
        self.channels = []
        # rabbitMQ: send
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_ip, port=5672))
        self.rabbitMQ_channel = self.connection.channel()
        self.rabbitMQ_channel.queue_declare(queue='bot2model')
        self.send_heartbeats.start()
        # rabbitMQ: recv
        def job(bot):
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_ip, port=5672))
            channel = connection.channel()
            channel.queue_declare(queue='model2bot')
            def callback(ch, method, properties, body):
                Payload = body.decode("utf-8")
                channel_id, img = Payload.split(' +++ ')
                img = ast.literal_eval(img)
                bot.dispatch("recv_image", channel_id, img)
            channel.basic_consume(queue='model2bot', on_message_callback=callback, auto_ack=True)
            channel.start_consuming()
        self.t = Thread(target=job, args=[self])
        self.t.start()

    async def on_recv_image(self, channel_id, img):
        print("communication: model to bot")
        print('sending image to channel {}'.format(channel_id))
        img_buffer = io.BytesIO()
        img_buffer.write(img)
        img_buffer.seek(0)
        file = discord.File(fp=img_buffer, filename='image.png')
        channel = self.get_channel(int(channel_id))
        await channel.send("Lmfao", file=file)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_guild_join(self, guild):
        embed=discord.Embed(
            title="**Elon Ma**",
            description=f"""
                        Thanks for adding me to {guild.name}!
                        **Usage**
                        1. `?crawling`: crawl the newest Elon Musk tweets every minute
                        2. `?stop_crawling`: stop crawling
                        3. `?image` + attach an image: change your face to Elon Ma
                        """,
            color=0xBABD42)
        await guild.text_channels[0].send(embed=embed)

    async def on_message(self, message):
        # we do not want the bot to reply to itself
        if message.author.id == self.user.id:
            return

        # verify command
        if not message.content.startswith('?'):
            return

        cmd = message.content[1:]
        if cmd == 'crawling':
            if message.channel.id in self.channels:
                await message.reply('error: crawling has already started in this channel.', mention_author=True)
                return
            self.channels.append(message.channel.id)
            if not self.get_tweets.is_running():
                # get the most recent tweet id
                response = crawler.get_users_tweets(user_id, max_results=5)
                self.most_recent_tweet_id = response.data[0].id
                response_demo = crawler.get_users_tweets(user_id_demo, max_results=5)
                self.most_recent_tweet_id_demo = response_demo.data[0].id
                # start task
                self.get_tweets.start()
            await message.reply('start crawling!', mention_author=True)
        elif cmd == 'stop_crawling':
            if not message.channel.id in self.channels:
                await message.reply('error: crawling hasn\'t started in this channel.', mention_author=True)
                return
            self.channels.remove(message.channel.id)
            if len(self.channels) == 0:
                # stop task
                self.get_tweets.stop()
            await message.reply('stop crawling!', mention_author=True)
        elif cmd == 'image':
            if len(message.attachments) != 1:
                await message.reply('error: please upload exactly one image.', mention_author=True)
                return
            # send channel id and image url to rabbitMQ
            print('communication: bot to model')
            print(message.channel.id)
            print(message.attachments[0].url)
            self.rabbitMQ_channel.basic_publish(exchange='', routing_key='bot2model', body=str(message.channel.id)+' +++ '+str(message.attachments[0].url))
        elif cmd == 'CD':
            await message.reply("Hi, everyone, I'm Elon Ma.", mention_author=True)
        else:
            await message.reply('unknown command!', mention_author=True)

    @tasks.loop(seconds=30)
    async def send_heartbeats(self):
        self.connection.process_data_events()

    @tasks.loop(seconds=30) # task runs every 30 seconds
    async def get_tweets(self):
        response = crawler.get_users_tweets(user_id, since_id=self.most_recent_tweet_id)
        print("most_recent_tweet_id: {}".format(self.most_recent_tweet_id))
        if response.data is not None:
            self.most_recent_tweet_id = response.data[0].id
            for tweet in response.data:
                print(tweet.id)
                print(tweet.text)
                for channel_ID in self.channels:
                    channel = self.get_channel(channel_ID)
                    await channel.send(tweet_url+str(tweet.id))
        response_demo = crawler.get_users_tweets(user_id_demo, since_id=self.most_recent_tweet_id_demo)
        print("most_recent_tweet_id_demo: {}".format(self.most_recent_tweet_id_demo))
        if response_demo.data is not None:
            self.most_recent_tweet_id_demo = response_demo.data[0].id
            for tweet in response_demo.data:
                print(tweet.id)
                print(tweet.text)
                for channel_ID in self.channels:
                    channel = self.get_channel(channel_ID)
                    await channel.send(tweet_url+str(tweet.id))

client = Bot(description='''just a trolling bot''')
client.run(bot_token)