from lottery import Lottery

if __name__ == '__main__':
    lottery = Lottery()
    lottery.load()
    lottery.validate_published_files()
    print('All published XSMN/XSMT feeds are valid.')
