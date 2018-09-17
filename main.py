from configparser import ConfigParser
import sys
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
        print("SendEmail failed")
        print(e)

def MonitorMail(section_name, config):
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
                    helpmessage="""
                    Valid commands
                        help - This message
                        Subscribe <list> subscribes to a mailing list
                        Unsubscribe <list> Will unsubscribe you from a mailing list
                        """
                    #msg['From']=config.get(section_name, "email_address")
                    msg['To']=email_message.get('From')
                    msg['Subject']="Help Message"
                    msg.attach(MIMEText(helpmessage, 'plain'))
                    #We need a different admin section to perform actions like subscribing
                    if 'help' in email_message.get('Subject').lower():
                        SendEmail(email_message.get('From'), msg.as_string(), "ADMIN", config)
                        client.move(uid, "LIST_ARCHIVE")
                else:
                    #here is where we decide if it's an command, or a message to pass along.
                    pass

    except Exception as e:
        print("An error occured\n")
        print(e)

























config=LoadConfig()
TestConfig(config)
for section_name in config.sections():

    MonitorMail(section_name, config)



