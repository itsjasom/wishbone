#imports
import discord
from datetime import datetime, timedelta, date
from discord.ext import tasks
import os
from dotenv import load_dotenv
load_dotenv()
import aiosqlite, asyncio
from pytz import timezone
tz = timezone('US/Eastern')

#setting channels for messages to be sent in via discord, for convenience 
wish_channel = 1011110363279937568
test_channel = 744003353633357827

client = discord.Client(intents=discord.Intents.all())

#list for how many wished per night
list = []

@client.event
#checks every message for certain scenarios
#usually checks if the message is sent in the wish channel, since the bot should only be usable there. 
async def on_message(message):
  if message.author.id == client.user.id:
    return
  
  #dates and times, used for calculating how long until the next 11:11, as well as the current date and time
  now = datetime.now(tz)
  current_time_s = now.strftime("%H:%M")
  current_time_other = now.strftime("%H:%M:%S")
  yesterday = now.today() - timedelta(days=1)
  yesterday = yesterday.strftime('%m/%d')
  timetil = (datetime.strptime("23:11:00", "%H:%M:%S") - datetime.strptime(current_time_other, "%H:%M:%S"))
  d = {"days": timetil.days}
  d["hours"], rem = divmod(timetil.seconds, 3600)
  d["minutes"], d["seconds"] = divmod(rem, 60)
  timetil = ("{hours}:{minutes}:{seconds}").format(**d)
  today = now.today()
  today = today.strftime('%m/%d')

#leaderboard for checking the statistics
  if message.channel.id == wish_channel and message.content == "!leaderboard":
    async with client.db.cursor() as cursor:
      #these lines create a list of the top five users, and their corresponding wish totals
      await cursor.execute("SELECT user FROM stats ORDER BY total DESC LIMIT 5")
      names = await cursor.fetchall()
      await cursor.execute("SELECT DISTINCT total FROM stats ORDER BY total DESC LIMIT 5")
      totals = await cursor.fetchall()
      
      #sends the message to the channel displaying the ranks
      if (len(totals) < 5 or len(names) < 5):
        await client.get_channel(wish_channel).send("Not enough wishers for a leaderboard!")
      else:
        em = discord.Embed(title=f"leaderboard", description=f"🥇: {client.get_user(*names[0]).name} - {str(*totals[0])} wishes\n🥈: {client.get_user(*names[1]).name} - {str(*totals[1])} wishes\n🥉: {client.get_user(*names[2]).name} - {str(*totals[2])} wishes\n4: {client.get_user(*names[3]).name} - {str(*totals[3])} wishes\n5: {client.get_user(*names[4]).name} - {str(*totals[4])} wishes")
        await client.get_channel(wish_channel).send(embed=em)
  await client.db.commit()

#individual stat checking
  if message.channel.id == wish_channel and message.content == "!stats":
    async with client.db.cursor() as cursor:
      #get the user's stats, and if they do not have any, set them at 0
      await cursor.execute("SELECT streak FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      streak = await cursor.fetchone()
      await cursor.execute("SELECT total FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      total = await cursor.fetchone()
      await cursor.execute("SELECT highest FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      highest = await cursor.fetchone()
      await cursor.execute("SELECT lastwish FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      lastwish = await cursor.fetchone()
      
      if not streak or not total or not highest:
        await cursor.execute("INSERT INTO stats (total, streak, highest, lastwish, user, guild) VALUES (?, ?, ?, ?, ?, ?)", (0, 0, 0, "", message.author.id, message.guild.id))
        
      try:
        streak = streak[0]
        total = total[0]
        highest = highest[0]
        lastwish = lastwish[0]
      except TypeError:
        streak = 0
        total = 0
        highest = 0
        lastwish = ""
        
    em = discord.Embed(title=f"{message.author.name}'s wish stats", description=f"current streak: {streak} days\ntotal: {total} wishes\nhighest streak: {highest} days\nlast wish: {lastwish}\ntime until next wish: {timetil}")
    await client.get_channel(wish_channel).send(embed=em)
  await client.db.commit()

#these lines allow me to set any given user's total and highest streak value
#this is for my own personal use, since the bot previously had a problem involving the data getting reset whenever the bot restarted
#the message.author.id checks if the user is me, so that not anybody can set their own values
  if message.channel.id == wish_channel and message.mentions and message.author.id == 498244948810792960:
    async with client.db.cursor() as cursor:
      if 'highest' in message.content:
        highest = int(message.content[:2])
        await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.mentions[0].id, message.guild.id))
      if 'total' in message.content:
        total = int(message.content[:2])
        await cursor.execute("UPDATE stats SET total = ? WHERE user = ? AND guild = ?", (total, message.mentions[0].id, message.guild.id))

  await client.db.commit()

#this checks if the time is 11:11 pm, and if the message was sent in the right channel
#it also checks if the user sending the message is accounted for in the data, and if not, it adds them (like before)
  if current_time_s == "23:11" and message.channel.id == wish_channel:
    async with client.db.cursor() as cursor:
      await cursor.execute("SELECT streak FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      streak = await cursor.fetchone()
      await cursor.execute("SELECT total FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      total = await cursor.fetchone()
      await cursor.execute("SELECT highest FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      highest = await cursor.fetchone()
      await cursor.execute("SELECT lastwish FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      lastwish = await cursor.fetchone()
  
      if not streak or not total or not highest:
        await cursor.execute("INSERT INTO stats (total, streak, highest, lastwish, user, guild) VALUES (?, ?, ?, ?, ?, ?)", (0, 0, 0, "", message.author.id, message.guild.id))
        
      try:
        streak = streak[0]
        total = total[0]
        highest = highest[0]
        lastwish = lastwish[0]
      except TypeError:
        streak = 0
        total = 0
        highest = 0
        lastwish = ""
        
      #if the message is "wish", and the time is 11:11, then the last wish date is set to the current day, and the total and streak are incremented by one. 
      #if the current streak is higher than the highest streak, the highest streak is set to the current streak
      #this also counts the user towards the daily wishers counter via the list
      if message.content.lower() == "wish" and message.author.name not in list:
        lastwish = today
        await cursor.execute("UPDATE stats SET lastwish = ? WHERE user = ? AND guild = ?", (lastwish, message.author.id, message.guild.id))
        total += 1
        await cursor.execute("UPDATE stats SET total = ? WHERE user = ? AND guild = ?", (total, message.author.id, message.guild.id))
        streak += 1
        await cursor.execute("UPDATE stats SET streak = ? WHERE user = ? AND guild = ?", (streak, message.author.id, message.guild.id))
        if streak > highest:
          highest = streak
          await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.author.id, message.guild.id))
        list.append(message.author.name)
  await client.db.commit()

  async with client.db.cursor() as cursor:
      await cursor.execute("SELECT streak FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      streak = await cursor.fetchone()
      await cursor.execute("SELECT total FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      total = await cursor.fetchone()
      await cursor.execute("SELECT highest FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      highest = await cursor.fetchone()
      await cursor.execute("SELECT lastwish FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      lastwish = await cursor.fetchone()
      
      if not streak or not total or not highest:
        await cursor.execute("INSERT INTO stats (total, streak, highest, lastwish, user, guild) VALUES (?, ?, ?, ?, ?, ?)", (0, 0, 0, "", message.author.id, message.guild.id))
        
      try:
        streak = streak[0]
        total = total[0]
        highest = highest[0]
        lastwish = lastwish[0]
      except TypeError:
        streak = 0
        total = 0
        highest = 0
        lastwish = ""
      
      #if the last time wished was not yesterday or today, and the user is not wishing, their streak is reset
      #if their streak was a new record, it replaces the highest streak
      if lastwish != yesterday and lastwish != today and message.content.lower() != "wish" and current_time_s != "23:11":
        if streak > highest:
          highest = streak
          await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.author.id, message.guild.id))
        streak = 0
        await cursor.execute("UPDATE stats SET streak = ? WHERE user = ? AND guild = ?", (streak, message.author.id, message.guild.id))
  await client.db.commit()

#this is all for testing purposes, so that I could experiment with the bot without the time needing to be 11:11. I made it so that the test functions only work in my own private server, so that they can't be abused
  if message.channel.id == test_channel:
    #testing
    async with client.db.cursor() as cursor:
      await cursor.execute("SELECT streak FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      streak = await cursor.fetchone()
      await cursor.execute("SELECT total FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      total = await cursor.fetchone()
      await cursor.execute("SELECT highest FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      highest = await cursor.fetchone()
      await cursor.execute("SELECT lastwish FROM stats WHERE user = ? AND guild = ?", (message.author.id, message.guild.id))
      lastwish = await cursor.fetchone()
  
      if not streak or not total or not highest:
        await cursor.execute("INSERT INTO stats (total, streak, highest, lastwish, user, guild) VALUES (?, ?, ?, ?, ?, ?)", (0, 0, 0, "", message.author.id, message.guild.id))
        
      try:
        streak = streak[0]
        total = total[0]
        highest = highest[0]
        lastwish = lastwish[0]
      except TypeError:
        streak = 0
        total = 0
        highest = 0
        lastwish = ""
        
      #resets the numbers to 0, so that I can see the effect of a given action more clearly
      if message.content == "reset":
          total = 0
          await cursor.execute("UPDATE stats SET total = ? WHERE user = ? AND guild = ?", (total, message.author.id, message.guild.id))
          streak = 0
          await cursor.execute("UPDATE stats SET streak = ? WHERE user = ? AND guild = ?", (streak, message.author.id, message.guild.id))
          highest = 0
          await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.author.id, message.guild.id))
          lastwish = ""
          await cursor.execute("UPDATE stats SET lastwish = ? WHERE user = ? AND guild = ?", (lastwish, message.author.id, message.guild.id))
        
      #simulates a wish, but can work at any time
      if message.content == "wish":
        lastwish = today
        await cursor.execute("UPDATE stats SET lastwish = ? WHERE user = ? AND guild = ?", (lastwish, message.author.id, message.guild.id))
        total += 1
        await cursor.execute("UPDATE stats SET total = ? WHERE user = ? AND guild = ?", (total, message.author.id, message.guild.id))
        streak += 1
        await cursor.execute("UPDATE stats SET streak = ? WHERE user = ? AND guild = ?", (streak, message.author.id, message.guild.id))
        if streak > highest:
          highest = streak
          await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.author.id, message.guild.id))
        
      #simulates a missed day of wishing, also works at any time  
      if message.content == "miss":
        if streak > highest:
          highest = streak
          await cursor.execute("UPDATE stats SET highest = ? WHERE user = ? AND guild = ?", (highest, message.author.id, message.guild.id))
        streak = 0
        await cursor.execute("UPDATE stats SET streak = ? WHERE user = ? AND guild = ?", (streak, message.author.id, message.guild.id))

    #functions similarly to !stats
    if message.content == "test":
        em = discord.Embed(title=f"{message.author.name}'s test stats", description=f"current streak: {streak} days\ntotal: {total} wishes\nhighest streak: {highest} days\nlast wish: {lastwish}\ntime until next wish: {timetil}")
        await client.get_channel(test_channel).send(embed=em)
  await client.db.commit()

#checks every second whether or not the current time is 11:10, and if it is, it reminds everyone (who wanted to be notified) that it's almost time to wish
#it says wish at 11:11, and then sends the amount of wishers on a given night at 11:12
@tasks.loop(seconds=1)
async def sendmessage():
     now = datetime.now(tz)
     current_time = now.strftime("%H:%M:%S")
     if current_time == "23:10:00":
       await client.get_channel(wish_channel).send("<@&1011835833185210490> almost wish time")
     if current_time == "23:11:00":
       await client.get_channel(wish_channel).send("wish")
       list.clear()
     if current_time == "23:12:00":
       await client.get_channel(wish_channel).send(str(len(list)) + " wishers tonight")
       list.clear()

#signals to me that the bot is working, also starts the loop that checks every second
@client.event
async def on_ready():
    print("I'm in")
    print(client.user)
    sendmessage.start()

#sets up the database
async def setup():
	client.db = await aiosqlite.connect("stats.db")
	await client.db.execute("CREATE TABLE IF NOT EXISTS mytable (column1, column2)")
	await client.db.commit()

#runs the bot, and runs the function that sets up the database
asyncio.get_event_loop().run_until_complete(setup())
client.run(os.environ['DISCORD_BOT_SECRET'])