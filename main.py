from configparser import ConfigParser
import os.path
import sys
import random
import string
from imapclient import IMAPClient
import email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sqlite3
#first we gotta load the config
def LoadConfig():
    config = ConfigParser()
    try:
        config.read('config.ini')
    except:
        print("Unable to open config.ini")
        sys.exit()
    try:
        if "ADMIN" not in config.sections():
            print("You need an admin address")
            sys.exit()
        for section_name in config.sections():
            print('Section:', section_name)
            print(' Options:', config.options(section_name))


        
    except Exception as e:
        print(e)
    return config


def TestConfig(config):
    print("Testing logins")
    for section_name in config.sections():
        print("Testing", section_name)
        try:
            with IMAPClient(host=config.get(section_name, "imap_server")) as client:
                client.login(config.get(section_name, "imap_username"), config.get(section_name, "imap_password"))
                print("Login Successful\n")
                print("Checking required folders")
                if client.folder_exists("LIST_ARCHIVE"):
                    print("Archive folder exists")
                else:
                    print("LIST_ARCHIVE folder does not exist. Creating now")
                    client.create_folder("LIST_ARCHIVE")
                    print("Done")
        except Exception as e:
            print("An error occured\n")
            print(e)
            sys.exit()

def SendEmail(receiver, message, section_name, config):
    try:
        smtpObj = smtplib.SMTP(config.get(section_name, "smtp_server"), config.get(section_name, "smtp_port"))
        #too lazy to go fix it in the config rn
        if config.get(section_name, "smtp_tls").lower()=="true":
            smtpObj.starttls()

        smtpObj.login(config.get(section_name, "smtp_username"), config.get(section_name, "smtp_password"))
        smtpObj.sendmail(config.get(section_name, "smtp_username"), receiver, message)
    except Exception as e:
        print("An error occured in the SendEmail() function")
        print(e)

def MonitorMail(section_name, config):
    #These are hardcoded for a reason.
    helpmessage="""
Valid commands
help - This message
Subscribe <list> subscribes to a mailing list
Unsubscribe <list> Will unsubscribe you from a mailing list
"""
    try:
         with IMAPClient(host=config.get(section_name, "imap_server")) as client:
            client.login(config.get(section_name, "imap_username"), config.get(section_name, "imap_password"))
            client.select_folder('INBOX')
            messages=client.search()
            for uid, message_data in client.fetch(messages, 'RFC822').items():
                email_message = email.message_from_bytes(message_data[b'RFC822'])
                print(email_message.get('From'), email_message.get('Subject'))
                if section_name=="ADMIN":
                    msg=MIMEMultipart()
                    msg['From']=config.get(section_name, "email_address")
                    msg['To']=email_message.get('From')
                    msg['Subject']="Help Message"
                    msg.attach(MIMEText(helpmessage, 'plain'))
                    #We need a different admin section to perform actions like subscribing
                    if 'help' in email_message.get('Subject').lower():
                        SendEmail(email_message.get('From'), msg.as_string(), "ADMIN", config)
                        client.move(uid, "LIST_ARCHIVE")
                    #I probably want to move this bit to it's own function. maybe later (never)
                    if "subscribe" in email_message.get("Subject").lower():
                        try:
                            Subscribe(email_message, section_name, config)
                            client.move(uid, "LIST_ARCHIVE")
                        except Exception as e:
                            print("An error occured in the Subscribe() function")
                            print(e)
    

                else:
                    #here is where we decide if it's an command, or a message to pass along.
                    if "subscribe" in email_message.get("Subject").lower():
                        msg=MIMEMultipart()
                        msg['From']=config.get(section_name, "email_address")
                        msg['To']=email_message.get('From')
                        msg['Subject']="Please send the subscribe request to {}", config.get("ADMIN", "email_address")
                        SendEmail(email_message.get('From'), msg.as_string(), section_name, config)

                    else:
                        SendToList(email_message, section_name, config)

    except Exception as e:
        print("An error occured in the mailmonitor function\n")
        print(e)

def GenerateConfirmationString(email_address, section_name):
    #This feature is here to stop someone being able to spoof an email and get someone else on the list - we have to implement this
    #because we are can't trust the mail server. a lot of mail servers don't stop spoofing.
    confirmation_string=''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    try:
        c,conn=MailSQL()
        c.execute("INSERT INTO mailer VALUES (?, ?, ?, ?)",(GetUserEmailAddress(email_address), section_name.lower(), confirmation_string, 0))
        conn.commit()
        conn.close()
        return(confirmation_string)
    except Exception as e:
        print("An error occured in the GenerateConfirmationString() function")
        print(e)
    

def CreateDatabase():
    print("Checking if mailer.db exists.")
    if os.path.isfile('mailer.db'):
        print("mailer.db exists. There is no option to re-write it here. please move or delete it if you want to rebuild it\n")
        return 0
    try:
        print("mailer.db does not exist. creating now")
        conn=sqlite3.connect('mailer.db')
        c=conn.cursor()
        c.execute("""
            CREATE TABLE mailer(email_address text, mailing_list text, confirmation_string text, subscribed int)""")
        conn.commit()
        conn.close()
        print("Created new database mailer.db")
    except Exception as e:
        print("An Error occured in the CreatDatabase function")
        print(e)


def MailSQL():
    conn=sqlite3.connect('mailer.db')
    c=conn.cursor()
    return(c,conn)

def GetUserEmailAddress(email_from):
    #This is a silly hack and I don't like it. but it works.
    email_from=email_from.split("<")
    return str(email_from[1].replace(">", ""))
    
    
    
def CheckIfSubscribed(email_message, section_name):
    c,conn=MailSQL()
    print("getting data")
    user_info=(GetUserEmailAddress(email_message.get('From')), section_name.lower())
    c.execute("SELECT * FROM mailer WHERE email_address=? AND mailing_list=?", (user_info))
    m=c.fetchone()
    print(m)
    if m==None:
        conn.close()
        return 1
    if m[3]==1:
        conn.close()
        return 0
    if m[2] in email_message.get('Subject'):
        #This is where we confirm the subscription
        m=c.execute("UPDATE mailer SET subscribed=1 WHERE email_address=? AND mailing_list=?", (user_info))
        conn.commit()
        conn.close()
        return 2

def SendToList(email_message,section_name,config):
    pass

def Subscribe(email_message,section_name,config):
    #These are hardcoded for a reason.

    subscribe_message="""
Your have asked to be subscribed to {maillist}
{email}
If you did not request this, you may disregard this message.
To confirm subscription, please reply to this message and leave the subject the same.

Thanks.
"""
    subscription_confirm="""
You have subscribed to {maillist}

To unsubscribe send an email to {email} or {admin_email} with the subject "unsubscribe technology"
"""
    for section_name in config.sections():
        if section_name.lower() in email_message.get("Subject").lower():
            try:
                is_subscribed=CheckIfSubscribed(email_message, section_name)
            except Exception as e:
                print("An error occured in the CheckIfSubscribed() function")
                print(e)
            msg=MIMEMultipart()
            msg['From']=config.get("ADMIN", "email_address")
            msg['To']=email_message.get('From')
            subscription=email_message.get("Subject").lower()
            subscription=subscription.replace(" ", "")
            subscription=subscription.split("subscribe")
            subscription=subscription[1]
            if is_subscribed==1:
                print("New subscriber!")
                msg['Subject']="Subscribe {} - {}".format(subscription, GenerateConfirmationString(email_message.get('From'), section_name))
                mailbody=subscribe_message.format(maillist=subscription, email=config.get(subscription.capitalize(), "email_address"))
                msg.attach(MIMEText(mailbody, 'plain'))
                SendEmail(email_message.get('From'), msg.as_string(), "ADMIN", config)
            if is_subscribed==2:
                print("Subscriber - Just confirmed!")
                subscription=subscription.split('-')
                msg['Subject']="Subscription to {} confirmed".format(subscription[0])
                #another annoying hack
                mailbody=subscription_confirm.format(maillist=subscription[0],email=config.get(subscription[0].capitalize(), "email_address"), admin_email=config.get("ADMIN", "email_address"))
                msg.attach(MIMEText(mailbody, 'plain'))
                print(mailbody)
                SendEmail(email_message.get('From'), msg.as_string(), "ADMIN", config)
                #this one here means they have sent a subscribe command - but haven't confirmed yet
                pass
            else:
                #do nothing. we don't need to respond if they are trying to subscribe to a list they are already subbed to.
                return 0

config=LoadConfig()
TestConfig(config)
CreateDatabase()
for section_name in config.sections():

    MonitorMail(section_name, config)



