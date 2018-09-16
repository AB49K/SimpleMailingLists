from configparser import ConfigParser
import sys
from imapclient import IMAPClient


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
        try:
            with IMAPClient(host=config.get(section_name, "imap_server")) as client:
                client.login(config.get(section_name, "imap_username"), config.get(section_name, "imap_password"))

        except Exception as e:
            print("An error occured\n")
            print(e)



config=LoadConfig()
TestConfig(config)
