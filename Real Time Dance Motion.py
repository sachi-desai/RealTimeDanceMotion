
from pykinect2 import PyKinectV2
from pykinect2.PyKinectV2 import *
from pykinect2 import PyKinectRuntime

import threading
import wave
import pyaudio
import ctypes
import random, math
import _ctypes
import pygame
import os, sys
import librosa, pickle
from aubio import source, tempo
from numpy import median, diff

# text input module cited from https://github.com/Nearoo/pygame-text-input
import pygame_textinput

if sys.hexversion >= 0x03000000:
    import _thread as thread
else:
    import thread

# colors for drawing different bodies 
SKELETON_COLORS = [pygame.color.THECOLORS["red"], 
                  pygame.color.THECOLORS["blue"], 
                  pygame.color.THECOLORS["green"], 
                  pygame.color.THECOLORS["orange"], 
                  pygame.color.THECOLORS["purple"], 
                  pygame.color.THECOLORS["yellow"], 
                  pygame.color.THECOLORS["violet"]]


#create global variables for controlling all running threads
musicRunning = True
musicLock = threading.Lock()

showEndScreen = False

#calculates tempo given a file path to wav audio
#I adapted the following two functions from https://github.com/aubio/aubio/blob/master/python/demos/demo_bpm_extract.py
def get_file_bpm(path, params=None):
    
    if params is None:
        params = {}
    # default:
    samplerate, win_s, hop_s = 44100, 1024, 512
    
    s = source(path, samplerate, hop_s)
    samplerate = s.samplerate
    o = tempo("specdiff", win_s, hop_s, samplerate)
    # List of beats, in samples
    beats = []
    # Total number of frames read
    total_frames = 0

    while True:
        samples, read = s()
        is_beat = o(samples)

        if is_beat:
            this_beat = o.get_last_s()
            beats.append(this_beat)
            
        total_frames += read
        if read < hop_s:
            break

    def beats_to_bpm(beats, path):

        # if enough beats are found, convert to periods then to bpm
        if len(beats) > 1:
            if len(beats) < 4:
                print("few beats found in {:s}".format(path))
            bpms = 60./diff(beats)
            return median(bpms)

        else:
            print("not enough beats found in {:s}".format(path))
            return 0

    return beats_to_bpm(beats, path)


class playGameMusic(threading.Thread):
    
    #plays audio while app continues its program at the same time
    #formatting adapted from https://people.csail.mit.edu/hubert/pyaudio/docs/

    def __init__(self, path):
        #filepath acts as the directions to the music I want to play
        super().__init__()
        self.path = os.path.abspath(path)
        self.framesInBuffer = 1024
        self.isRunning = True

        #audio object in READ ONLY mode 
        self.wavFile = wave.open(self.path, 'rb')
        self.p = pyaudio.PyAudio()

        self.stream = self.p.open(format = self.p.get_format_from_width(self.wavFile.getsampwidth()),
            channels = self.wavFile.getnchannels(),
            rate = self.wavFile.getframerate(),
            output = True)

        self.game = RunJustDance()


    def run(self):

        data = self.wavFile.readframes(self.framesInBuffer)

        while len(data) > 0:

            if not musicRunning:
                self.game.displayEndScreen()
                return

            self.stream.write(data)
            data = self.wavFile.readframes(self.framesInBuffer)

        self.stream.close()
        self.p.terminate()


    def play(self):
        #gets the music to start playing
        self.start()



# game loop structure adapted from Omisa Jinsi Kinect for Windows v2 Body Game
# https://tinyurl.com/uhzbzss
class RunJustDance(object):
    def __init__(self):
        pygame.init()

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Set the width and height of the screen [width, height]
        self._infoObject = pygame.display.Info()
        self._screen = pygame.display.set_mode((950, 600), 
                                               pygame.HWSURFACE|pygame.DOUBLEBUF|pygame.RESIZABLE, 32)

        self.width = self._screen.get_width()
        self.height = self._screen.get_height()
        pygame.display.set_caption("Real Time Dance Motion")

        # Loop until the user clicks the close button.
        self._done = False

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Kinect runtime object, we want only color and body frames 
        self._kinect = PyKinectRuntime.PyKinectRuntime(PyKinectV2.FrameSourceTypes_Color | PyKinectV2.FrameSourceTypes_Body)

        # back buffer surface for getting Kinect color frames, 32bit color, width and height equal to the Kinect color frame size
        self._frame_surface = pygame.Surface((self._kinect.color_frame_desc.Width, self._kinect.color_frame_desc.Height), 0, 32)

        # here we will store skeleton data 
        self._bodies = None

        self.curRightWristHeight = 0
        self.curRightWristWidth = 0

        self.curLeftWristHeight = 0
        self.curLeftWristWidth = 0

        self.curRightElbowHeight = 0
        self.curRightElbowWidth = 0

        self.curLeftElbowHeight = 0
        self.curLeftElbowWidth = 0
        
        self.curSpineHeight = 0
        self.curSpineWidth = 0

        self.prevRightWristHeight = 0
        self.prevRightWristWidth = 0

        self.prevLeftWristHeight = 0
        self.prevLeftWristWidth = 0

        self.prevRightElbowHeight = 0
        self.prevRightElbowWidth = 0

        self.prevLeftElbowHeight = 0
        self.prevLeftElbowWidth = 0
        
        self.prevSpineHeight = 0
        self.prevSpineWidth = 0

        self.curHeadHeight = 0
        self.curHeadWidth = 0

        self.curNeckHeight = 0
        self.curNeckWidth = 0

        self.curRightHipHeight = 0
        self.curRightHipWidth = 0

        self.curLeftHipHeight = 0
        self.curLeftHipWidth = 0

        #increments after a certain amount of time, and used to index in getMove function
        self.moveCount = 0

        self.imageDx = 0
        self.prevIndex = self.moveCount

        self.error = None
        self.currMoveType = None
        self.score = 0
        self.subscore = 0
        self.countdown = 3

        #these values will change based upon user choices in level screen and song choice screens
        self.level = None
        self.song = None
        self.songBPM = 0
        self.timePerMove = 0

        self.playerName = None

        #define some useful colors
        self.white = (255, 255, 255)
        self.blue = (0, 0, 128)
        self.pink = (255,192,203)
        self.purple = (228, 207, 255)
        self.green = (0, 240, 110)
        self.gray = (211,211,211)
        self.black = (0, 0, 0)
        self.mauve = (161, 113, 136)

        #load the dance moves images

        #cited from http://clipart-library.com/clipart/LTdoAkBpc.htm
        self.discoImg = pygame.image.load('disco.png')

        #cited from https://tinyurl.com/tj8pnkq
        self.goalpostImg = pygame.image.load('goalpost.png')
        
        #cited from http://getdrawings.com/dab-silhouette#dab-silhouette-16.jpg
        self.dabImg = pygame.image.load('dabbing.png')
        
        #cited from http://clipartmag.com/hip-hop-dancing-clipart#hip-hop-dancing-clipart-13.jpg
        self.hipHopImg = pygame.image.load('hip_hop.png')

        #load images for start screen

        #cited from https://www.pngkey.com/png/full/486-4864675_dancer-just-dance.png
        self.coverImg1 = pygame.image.load('cover_image_1.png')

        #cited from https://tinyurl.com/rydwj5l
        self.coverImg2 = pygame.image.load('cover_image_2.png')

        #gives player a chance to copy move, then scores after 'move lifetime'
        self.switch_image_event = pygame.USEREVENT + 1

        #timer events created for countdown screen before game starts
        self.increment_countdown_event = pygame.USEREVENT + 2
        self.change_countdown = 1300
        
        #keep move image on screen for 5 seconds
        self.keep_image = 5000

        #as the player moves towards the final position, don't increment subscores at each frame
        #add every second, to make it seem as if it is analyzing each frame
        self.add_subscore_event = pygame.USEREVENT + 3
        self.increment_subscore = 1000

        pygame.time.set_timer(self.switch_image_event, self.keep_image)

        self.moveAccuracies = dict()

        #generates a new moves list for each game call
        self.movesList = []
        

    def displayMoveImage(self, moveType, imageDx):
        
        if moveType == 'disco':
            curImage = self.discoImg

        elif moveType == 'goalpost':
            curImage = self.goalpostImg

        elif moveType == 'dab':
            curImage = self.dabImg

        elif moveType == 'hiphop':
            curImage = self.hipHopImg
        
        pygame.transform.scale(curImage, (400, 600))

        imageCenter = ((5/6)*(self._frame_surface.get_width()) + imageDx, 
            (5/6)*(self._frame_surface.get_height()))

        self._frame_surface.blit(curImage, imageCenter)
        curImage = None

    def displayStartScreen(self):

        self._screen.fill(self.blue)
        self.createTextBlock('Welcome to Real Time Dance Motion!', self.width//2, self.height//2, self.white, 40)
        self.createTextBlock('Press the SPACE key to begin', self.width//2, 0.85*(self.height), self.white, 25)
        
        self.coverImg1 = pygame.transform.scale(self.coverImg1, (180, 250))
        self.coverImg2 = pygame.transform.scale(self.coverImg2, (130, 240))

        center1 = ((3/4)*self.width,(0.567)*self.height)
        center2 = ((0.05)*self.width, (0.05)*self.height)

        self._screen.blit(self.coverImg1, center1)
        self._screen.blit(self.coverImg2, center2)

        pygame.display.flip()
        self.pauseUntilKeypressed()
  


    def displayLevelScreen(self):

        self._screen.fill(self.purple)
        self.createTextBlock('Choose a difficulty level below:', self.width//2, self.height//8, self.white, 30)
        pygame.display.flip()

        #create the buttons and have the player interact with them
        freeze = True
        while freeze:
            self._clock.tick(60)
            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()

                if event.type == pygame.mouse.get_pressed:
                    paused = False

            #if the player hovers mouse over a button, then it should become highlighted
            mouseX, mouseY = pygame.mouse.get_pos()

            # collect all button click actions
            mouseDown, mouseUp, mouseMove = pygame.mouse.get_pressed()

            easyRectX, easyRectY = 200, 200
            
            diffRectX, diffRectY = 200, 400
            
            rectWidth, rectHeight = 550, 100

            #easy level button
            if ((mouseX > easyRectX and mouseX < easyRectX + rectWidth) and
                (mouseY > easyRectY and mouseY < easyRectY + rectHeight)):

                pygame.draw.rect(self._screen, self.white,
                    (easyRectX, easyRectY, rectWidth, rectHeight), 10)

                #check if the player actually clicked this button
                if mouseDown == 1:
                    self.level = 'easy'
                    print(self.level)
                    self.displaySongChoiceScreen()

            else:

                pygame.draw.rect(self._screen, self.white,
                    (easyRectX, easyRectY, rectWidth, rectHeight))

            self.createTextBlock('Easy', 200 + (rectWidth//2), 200 + (rectHeight//2), self.blue, 28)

            #difficult level button
            if ((mouseX > diffRectX and mouseX < diffRectX + rectWidth) and
                (mouseY > diffRectY and mouseY < diffRectY + rectHeight)):

                pygame.draw.rect(self._screen, self.white,
                    (diffRectX, diffRectY, rectWidth, rectHeight), 10)

                #check if the player actually clicked this button
                if mouseDown == 1:
                    self.level = 'difficult'
                    print(self.level)
                    self.displaySongChoiceScreen()

            else:

                pygame.draw.rect(self._screen, self.white,
                    (diffRectX, diffRectY, rectWidth, rectHeight))

            self.createTextBlock('Difficult', 200 + (rectWidth//2), 400 + (rectHeight//2), self.blue, 28)
            
            pygame.display.flip()


    def displaySongChoiceScreen(self):

        self._screen.fill(self.pink)
        self.createTextBlock('Choose a song below:', self.width//2, self.height//8, self.white, 35)
        pygame.display.flip()

        #create the buttons and have the player interact with them
        freeze = True
        while freeze:
            self._clock.tick(60)
            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()

                if event.type == pygame.mouse.get_pressed:
                    paused = False

            #if the player hovers mouse over a button, then it should become highlighted
            mouseX, mouseY = pygame.mouse.get_pos()

            # collect all button click actions
            mouseDown, mouseUp, mouseMove = pygame.mouse.get_pressed()

            option1X, option1Y = 200, 150
            
            option2X, option2Y = 200, 300
            
            option3X, option3Y = 200, 450

            rectWidth, rectHeight = 550, 75

            #song choice 1 button
            if ((mouseX > option1X and mouseX < option1X + rectWidth) and
                (mouseY > option1Y and mouseY < option1Y + rectHeight)):

                pygame.draw.rect(self._screen, self.white,
                    (option1X, option1Y, rectWidth, rectHeight), 10)

                #check if the player actually clicked this button
                if mouseDown == 1:
                    #music cited from https://youtu.be/InOCRXEsK3M
                    self.song = '7 Rings.wav'
                    self.songBPM = get_file_bpm(self.song, params = {})
                    self.generateMovesList()
                    self.displayInstructionScreen()
                    
            else:

                pygame.draw.rect(self._screen, self.white,
                    (option1X, option1Y, rectWidth, rectHeight))

            self.createTextBlock('7 Rings by Ariana Grande', option1X + (rectWidth//2), option1Y + (rectHeight//2), self.blue, 28)

            #song choice 2 button
            if ((mouseX > option2X and mouseX < option2X + rectWidth) and
                (mouseY > option2Y and mouseY < option2Y + rectHeight)):

                pygame.draw.rect(self._screen, self.white,
                    (option2X, option2Y, rectWidth, rectHeight), 10)

                #check if the player actually clicked this button
                if mouseDown == 1:
                    #music cited from https://youtu.be/4-TbQnONe_w
                    self.song = 'Bad Guy.wav'
                    self.songBPM = get_file_bpm(self.song, params = {})
                    self.generateMovesList()
                    self.displayInstructionScreen()

            else:

                pygame.draw.rect(self._screen, self.white,
                    (option2X, option2Y, rectWidth, rectHeight))

            self.createTextBlock('Bad Guy by Billie Eilish', option2X + (rectWidth//2), option2Y + (rectHeight//2), self.blue, 28)

            #song choice 3 button
            if ((mouseX > option3X and mouseX < option3X + rectWidth) and
                (mouseY > option3Y and mouseY < option3Y + rectHeight)):

                pygame.draw.rect(self._screen, self.white,
                    (option3X, option3Y, rectWidth, rectHeight), 10)

                #check if the player actually clicked this button
                if mouseDown == 1:
                    #music cited from https://youtu.be/pOznx1KLN7U
                    self.song = 'Baby Shark.wav'
                    self.songBPM = get_file_bpm(self.song, params = {})
                    self.generateMovesList()
                    self.displayInstructionScreen()

            else:

                pygame.draw.rect(self._screen, self.white,
                    (option3X, option3Y, rectWidth, rectHeight))

            self.createTextBlock('Baby Shark', option3X + (rectWidth//2), option3Y + (rectHeight//2), self.blue, 28)
            
            pygame.display.flip()

        
    def generateMovesList(self):

        possibleMoves = ['goalpost', 'disco', 'hiphop', 'dab']

        for move in possibleMoves:
            self.moveAccuracies[move] = None

        #use the song tempo to generate the amount of moves to produce throughout entire song
        #give player 8 beats to complete each move
        
        #convert BPM to BPS
        songBPS = self.songBPM / 60
        

        #solve for amount of time each move should stay on screen
        inverseSec = songBPS / 8
        
        timePerMove = 1/inverseSec

        #generate amount of moves based upon how much time each move is on the screen
        songLength = librosa.core.get_duration(filename=self.song)
        numMoves = int(songLength/timePerMove)
       
        #convert to milliseconds
        self.timePerMove = int(timePerMove * 1000)

        for _ in range(numMoves):
            #generate the possible moves list
            self.movesList.append(random.choice(possibleMoves))



    def displayInstructionScreen(self):

        self._screen.fill(self.white)
        pygame.display.flip()
        
        #image cited from https://wallpapersafari.com/w/AFfy7n
        backgroundImg = pygame.image.load('background_img.png')

        scaledBackground = pygame.transform.scale(backgroundImg, (self.width, self.height))

        center = (0, 0)

        self._screen.blit(backgroundImg, center)

        startX, startY = 0.1*self.width, 0.1*self.height
        endX, endY = 0.8*self.width, 0.8*self.height

        pygame.draw.rect(self._screen, self.blue, (startX, startY, endX, endY))

        self.createTextBlock("Here's How to Play:", self.width//2, self.height//4, self.white, 35)
        
        self.createTextBlock("A picture will move across the screen, showing you the dance move.",
            self.width//2, (3/8)*self.height, self.white, 16)

        self.createTextBlock('You have 8 beats to get to that move, and the game will score your accuracy!',
            self.width//2, (7/16)*self.height, self.white, 16)

        self.createTextBlock('When you finish, it will give you feedback on how to score better next time.',
            self.width//2, (1/2)*self.height, self.white, 16)

        self.createTextBlock('Good luck, and have fun!',
            self.width//2, (9/16)*self.height, self.white, 16)

        self.createTextBlock("When you're ready, press the SPACE key",
            self.width//2, (11/16)*self.height, self.white, 25)

        pygame.display.flip()
        self.pauseUntilKeypressed()
        self.displayCountdownScreen()

    def displayCountdownScreen(self):

        pygame.display.flip()

        pygame.time.set_timer(self.increment_countdown_event, self.change_countdown)

        while True:
            self._screen.fill(self.blue)
            self.createTextBlock('Are you ready?', self.width//2, self.height//4, self.white, 35)
        
            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    quit()
                    pygame.quit()

                if event.type == self.increment_countdown_event:
                    if self.countdown > 0:
                        self.countdown -= 1
                    else:
                        self.run()

            fontSize = 65
            countdownFont = pygame.font.SysFont("baskerville", fontSize)
            countdownText = countdownFont.render(f'Starting in {self.countdown} ...', True, self.white)
            w , h = self.width//2, self.height//2
            txt = countdownText.get_rect()
            txt.center = (w, h)
            self._screen.blit(countdownText, txt)

            pygame.display.update()

            pygame.display.flip()

            self._clock.tick(60)
            

    def getFeedback(self):
        feedbackString = ''
        for move in self.moveAccuracies:
            comment = self.moveAccuracies[move]
            if comment != None:
                feedbackString = feedbackString + comment + '\n'

        return feedbackString


    def displayEndScreen(self):

        self._screen = pygame.display.set_mode((self.width, self.height))
        self._screen.fill(self.mauve)
        self.createTextBlock("Congrats, you've completed Real Time Dance Motion!", self.width//2, self.height//6, self.white, 35)
        numMoves = len(self.movesList)
        maxScore = numMoves*25
        self.createTextBlock(f"Final Score: {self.score} / {maxScore}", self.width//2, self.height//3, self.white, 28)
        self.createTextBlock(f"Here's some feedback!", self.width//2, 0.5*self.height, self.white, 28)

        pygame.display.flip()

        comments = self.getFeedback()

        commentsList = comments.splitlines()
        print(commentsList)

        commentHeight = (3/5)*self.height
        spacing = 0.05*self.height

        self.createTextBlock(commentsList[0], self.width//2, commentHeight, self.white, 15)
        self.createTextBlock(commentsList[1], self.width//2, commentHeight + spacing, self.white, 15)
        self.createTextBlock(commentsList[2], self.width//2, commentHeight + 2*spacing, self.white, 15)
        self.createTextBlock(commentsList[3], self.width//2, commentHeight + 3*spacing, self.white, 15)

        self.createTextBlock('Press the red X on the top right of the screen to enter your name,',
            self.width//2, commentHeight + 5*spacing, self.white, 18)
        
        self.createTextBlock('then click it again to view the top scores!',
            self.width//2, commentHeight + 5*spacing, self.white, 18)
        
        pygame.display.flip()
        self.pauseUntilKeypressed()
        self.getPlayerName()
        
#the function below is adapted from documentation found at https://github.com/Nearoo/pygame-text-input
    def getPlayerName(self):

        player = pygame_textinput.TextInput()
        screen = pygame.display.set_mode((400, 200))
        gettingText = True

        while gettingText:

            screen.fill(self.gray)
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    quit()

                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_RIGHT:
                        self.displayScoreboard()

                    
            if player.update(events):
                self.playerName = player.get_text()
                self.displayScoreboard()

            #every time text is entered, the screen is updated
            screen.blit(player.get_surface(), (10, 10))

            pygame.display.update()
            self._clock.tick(30)

        

    def displayScoreboard(self):

        playersList, scoresList = self.getTopFiveScores()
        self._screen = pygame.display.set_mode((self.width, self.height))
        
        self._screen.fill(self.white)
        
        #image cited from https://wallpapersafari.com/w/AFfy7n
        backgroundImg = pygame.image.load('background_img.png')

        scaledBackground = pygame.transform.scale(backgroundImg, (self.width, self.height))

        center = (0, 0)

        self._screen.blit(backgroundImg, center)
        startX, startY = 0.1*self.width, 0.1*self.height
        endX, endY = 0.8*self.width, 0.8*self.height

        pygame.draw.rect(self._screen, self.gray, (startX, startY, endX, endY))

        self.createTextBlock("Highest Scores:", self.width//2, self.height//4, self.white, 35)

        self.createTextBlock(f'{playersList[4]}\t\t{scoresList[4]}', self.width//2, (3/8)*self.height, self.black, 25)
        self.createTextBlock(f'{playersList[3]}\t\t{scoresList[3]}', self.width//2, (1/2)*self.height, self.black, 25)
        self.createTextBlock(f'{playersList[2]}\t\t{scoresList[2]}', self.width//2, (5/8)*self.height, self.black, 25)
        self.createTextBlock(f'{playersList[1]}\t\t{scoresList[1]}', self.width//2, (6/8)*self.height, self.black, 25)
        self.createTextBlock(f'{playersList[0]}\t\t{scoresList[0]}', self.width//2, (7/8)*self.height, self.black, 25)
        pygame.display.flip()
        
        while True:

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit()


    def getTopFiveScores(self):
        score, name = self.score, self.playerName
        
        allTopScores = self.updateScoreboard(score, name)

        #given the current user's inputted name, and their score
        #we compare it with the other scores in scoreboard
        #and return the top five scores + player names

        scoresDict = dict()

        for score, player in allTopScores:
            scoresDict[player] = score

        orderedScores = sorted(scoresDict.keys())

        orderedPlayers = []
        for score in orderedScores:
            orderedPlayers.append(scoresDict[score])

        #all of them are ordered, so now we only want to return the top five
        print((orderedPlayers, orderedScores))
        if len(orderedScores) <= 5:
            return (orderedPlayers, orderedScores)
        else:
            return (orderedPlayers[0:5], orderedScores[0:5])

        
    #the function below is adapted from https://www.datacamp.com/community/tutorials/pickle-python-tutorial
    @staticmethod
    def updateScoreboard(player, score):
        
        file = 'scoreboard.txt'
        scoreAndNameList = list()

        if os.path.exists(file) and os.path.getsize(file) > 0:
            with open(file, 'rb') as rfp:
                prevScoresAndNames = pickle.load(rfp)

                scoreAndNameList.extend(prevScoresAndNames)
        
        scoreAndPlayer = score, player
        scoreAndNameList.append((scoreAndPlayer))

        with open(file, 'wb') as wfp:
            pickle.dump(scoreAndNameList, wfp)

        with open(file, 'rb') as rfp:
            scoreAndNameList = pickle.load(rfp)

        return scoreAndNameList


    def createTextBlock(self, message, cx, cy, color, fontSize):
        font = pygame.font.SysFont("georgia", fontSize, bold=True)
        title = font.render(message, True, color)
        textBlock = title.get_rect()
        textBlock.center = (cx, cy)
 
        self._screen.blit(title, textBlock)


    def pauseUntilKeypressed(self):
        paused = True
        while paused:
            self._clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    paused = False
                    self._done = True

                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_SPACE:
                        paused = False

                    if event.key == pygame.K_RIGHT:
                        self.displayEndScreen()


    def draw_body_bone(self, joints, jointPoints, color, joint0, joint1):
        joint0State = joints[joint0].TrackingState;
        joint1State = joints[joint1].TrackingState;

        # both joints are not tracked
        if (joint0State == PyKinectV2.TrackingState_NotTracked) or (joint1State == PyKinectV2.TrackingState_NotTracked): 
            return

        # both joints are not *really* tracked
        if (joint0State == PyKinectV2.TrackingState_Inferred) and (joint1State == PyKinectV2.TrackingState_Inferred):
            return

        # ok, at least one is good 
        start = (jointPoints[joint0].x, jointPoints[joint0].y)
        end = (jointPoints[joint1].x, jointPoints[joint1].y)

        try:
            pygame.draw.line(self._frame_surface, color, start, end, 8)
        except: # need to catch it due to possible invalid positions (with inf)
            pass

    def draw_body(self, joints, jointPoints, color):
        # Torso
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_Head, PyKinectV2.JointType_Neck);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_Neck, PyKinectV2.JointType_SpineShoulder);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineShoulder, PyKinectV2.JointType_SpineMid);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineMid, PyKinectV2.JointType_SpineBase);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineShoulder, PyKinectV2.JointType_ShoulderRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineShoulder, PyKinectV2.JointType_ShoulderLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineBase, PyKinectV2.JointType_HipRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_SpineBase, PyKinectV2.JointType_HipLeft);
    
        # Right Arm    
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_ShoulderRight, PyKinectV2.JointType_ElbowRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_ElbowRight, PyKinectV2.JointType_WristRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_WristRight, PyKinectV2.JointType_HandRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_HandRight, PyKinectV2.JointType_HandTipRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_WristRight, PyKinectV2.JointType_ThumbRight);

        # Left Arm
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_ShoulderLeft, PyKinectV2.JointType_ElbowLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_ElbowLeft, PyKinectV2.JointType_WristLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_WristLeft, PyKinectV2.JointType_HandLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_HandLeft, PyKinectV2.JointType_HandTipLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_WristLeft, PyKinectV2.JointType_ThumbLeft);

        # Right Leg
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_HipRight, PyKinectV2.JointType_KneeRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_KneeRight, PyKinectV2.JointType_AnkleRight);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_AnkleRight, PyKinectV2.JointType_FootRight);

        # Left Leg
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_HipLeft, PyKinectV2.JointType_KneeLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_KneeLeft, PyKinectV2.JointType_AnkleLeft);
        self.draw_body_bone(joints, jointPoints, color, PyKinectV2.JointType_AnkleLeft, PyKinectV2.JointType_FootLeft);


    def draw_color_frame(self, frame, target_surface):
        target_surface.lock()
        address = self._kinect.surface_as_array(target_surface.get_buffer())
        ctypes.memmove(address, frame.ctypes.data, frame.size)
        del address
        target_surface.unlock()

    @staticmethod
    def percentDifference(actual, expected):

        absDiff = abs(actual - expected)
        avg = (actual + expected) / 2
        if avg == 0:
            return 50
        percentDiff = (absDiff / avg) * 100
        return int(percentDiff)


    @staticmethod
    def distance(x1, y1, x2, y2):
        return ((x1 - x2)**2 + (y1 - y2)**2)**0.5

    @staticmethod
    def pythag(a, b):
        return ((a)**2 + (b)**2)**0.5


    def getGoalpostError(self):

        #most important check --> if it doesn't pass, automatic point deduction
        if (self.curRightElbowHeight > self.curSpineHeight and
            self.curLeftElbowHeight > self.curSpineHeight):

            x1, y1 = self.curLeftElbowWidth, self.curLeftElbowHeight
            x2, y2 = self.curLeftWristWidth, self.curLeftWristHeight

            leftElbowWristDist = self.distance(x1, y1, x2, y2)

            x3, y3 = self.curRightElbowWidth, self.curRightElbowHeight
            x4, y4 = self.curRightWristWidth, self.curRightWristHeight

            rightElbowWristDist = self.distance(x3, y3, x4, y4)

            x5, y5 = self.curSpineWidth, self.curSpineHeight

            leftElbowShoulderDist = self.distance(x1, y1, x5, y5)

            rightElbowShoulderDist = self.distance(x3, y3, x5, y5)

            leftShoulderWristDist = self.pythag(leftElbowWristDist, leftElbowShoulderDist)
            rightShoulderWristDist = self.pythag(rightElbowWristDist, rightElbowShoulderDist)

            if (math.acos(rightElbowShoulderDist/rightShoulderWristDist) < math.radians(50)
                and math.acos(leftElbowShoulderDist/leftShoulderWristDist) < math.radians(50)):
                firstError = 0

            else:
                firstError = 5

            x6, y6 = self.curLeftHipWidth, self.curLeftHipHeight
            x7, y7 = self.curRightHipWidth, self.curRightHipHeight

            leftShoulderHipDist = self.distance(x5, y5, x6, y6)
            rightShoulderHipDist = self.distance(x5, y5, x7, y7)

            leftElbowHipDist = self.pythag(leftShoulderHipDist, leftElbowShoulderDist)
            rightElbowHipDist = self.pythag(rightShoulderHipDist, rightElbowShoulderDist)

            #ideal angle is 90 degrees, so the other angles in the triangle should sum to 90
            
            #check left arm
            leftAngleSum = math.acos(leftShoulderHipDist/leftElbowHipDist) + math.acos(leftElbowShoulderDist/leftElbowHipDist)
            if leftAngleSum < math.radians(90):
                secondError = 5
                self.moveAccuracies['goalpost'] = 'Try to keep your left elbow higher when doing the goalpost move.'

            elif leftAngleSum > math.radians(90):
                secondError = 10
                self.moveAccuracies['goalpost'] = 'Try to keep your left elbow lower when doing the goalpost move.'
            
            else:
                secondError = 0
                self.moveAccuracies['goalpost'] = 'Great job, your stance in the goalpost move is perfect!'


            #check right arm
            rightAngleSum = math.acos(rightShoulderHipDist/rightElbowHipDist) + math.acos(rightElbowShoulderDist/rightElbowHipDist)
            if rightAngleSum < math.radians(90):
                secondError = 5
                self.moveAccuracies['goalpost'] = 'Try to keep your right elbow higher when doing the goalpost move.'

            elif rightAngleSum > math.radians(90):
                secondError = 10
                self.moveAccuracies['goalpost'] = 'Try to keep your right elbow lower when doing the goalpost move.'
            
            else:
                secondError = 0
                self.moveAccuracies['goalpost'] = 'Great job, your stance in the goalpost move is perfect!'

            avgError = (firstError + secondError)//2

        else:
            self.moveAccuracies['goalpost'] = 'Follow the right angles of the goalmost image more closely next time!'            
            avgError = 30


        return avgError

    def getDiscoError(self):

        if (self.curRightWristHeight > self.curRightElbowHeight and
            self.curRightElbowHeight > self.curSpineHeight ):

            x1, y1 = self.curLeftElbowWidth, self.curLeftElbowHeight
            x2, y2 = self.curLeftWristWidth, self.curLeftWristHeight

            leftElbowWristDist = self.distance(x1, y1, x2, y2)

            x3, y3 = self.curRightElbowWidth, self.curRightElbowHeight
            x4, y4 = self.curRightWristWidth, self.curRightWristHeight

            x5, y5 = self.curSpineWidth, self.curSpineHeight

            #compare the two slopes to make sure arm is completely straight
            rightElbowWristSlope = (y4 -y3)//(x4 - x3)

            rightElbowShoulderSlope = (y3 - y5)//(x3 - x5)

            if self.percentDifference(rightElbowWristSlope, rightElbowShoulderSlope) > 10:
                firstError = 10
                self.moveAccuracies['disco'] = 'Make sure your right arm is completely straight in disco.'
            else:
                firstError = 0
                self.moveAccuracies['disco'] = 'Your disco moves are great!'


            #left arm should be on the hip, so check the angles for that position
            leftElbowShoulderDist = self.distance(x1, y1, x5, y5)
            rightElbowShoulderDist = self.distance(x3, y3, x5, y5)

            #get vertical displacement between shoulder and hip
            shoulderToHipDist = self.curSpineHeight - self.curLeftHipHeight

            #divide the top and bottom half of triangle to make 2 right triangles
            halfShoulderHipDist = shoulderToHipDist // 2

            #check the angles of both subtriangles
            topAngle = math.acos(halfShoulderHipDist/leftElbowShoulderDist)
            bottomAngle = math.acos(halfShoulderHipDist/leftElbowWristDist)

            totAngle = topAngle + bottomAngle

            if totAngle < math.radians(60):
                secondError = 7
                self.moveAccuracies['disco'] = 'Keep your left arm lower on disco!'

            elif totAngle > math.radians(90):
                secondError = 10
                self.moveAccuracies['disco'] = 'Make sure your left arm is at waist height during disco.'

            else:
                secondError = 0
                self.moveAccuracies['disco'] = 'Your stance looks awesome for disco!'


            avgError = (firstError + secondError)//2

        else:
            avgError = 30
            self.moveAccuracies['disco'] = 'Keep your right arm higher in disco!'

        return avgError



    def getDabError(self):

        #this move is similar to disco in that the right arm should be completely straight
        #but the left arm in this case is higher than in disco
        if (self.curRightWristHeight > self.curRightElbowHeight and
            self.curRightElbowHeight > self.curSpineHeight ):

            x1, y1 = self.curLeftElbowWidth, self.curLeftElbowHeight
            x2, y2 = self.curLeftWristWidth, self.curLeftWristHeight

            leftElbowWristDist = self.distance(x1, y1, x2, y2)

            x3, y3 = self.curRightElbowWidth, self.curRightElbowHeight
            x4, y4 = self.curRightWristWidth, self.curRightWristHeight

            x5, y5 = self.curSpineWidth, self.curSpineHeight

            #compare the two slopes to make sure arm is completely straight
            rightElbowWristSlope = (y4 -y3)//(x4 - x3)

            rightElbowShoulderSlope = (y3 - y5)//(x3 - x5)

            if self.percentDifference(rightElbowWristSlope, rightElbowShoulderSlope) > 10:
                firstError = 10
                self.moveAccuracies['dab'] = 'Make sure your right arm is completely straight when you dab.'
            else:
                firstError = 0
                self.moveAccuracies['dab'] = 'Your arms look great when you dab!'


            #check slope of left elbow to wrist and elbow to shoulder, and compare
            #they should be almost the same
            leftElbowWristSlope = (y2 - y1)//(x2 - x1)
            leftElbowShoulderSlope = (y5 - y1)//(x5 -x1)

            if self.percentDifference(leftElbowWristSlope, leftElbowShoulderSlope) > 10:
                secondError = 10
                self.moveAccuracies['dab'] = 'You should keep your left elbow higher on the dab.'

            else:
                secondError = 0
                self.moveAccuracies['dab'] = 'Your dab looks great so far!'
            
            avgError = (firstError + secondError)//2

        else:
            avgError = 30
            self.moveAccuracies['dab'] = 'Keep your right arm needs to be higher in disco.'

        return avgError

        
    def getHipHopError(self):

        #initial check that both arms are above waist height
        if (self.curRightWristHeight > self.curRightHipHeight and 
            self.curLeftWristHeight > self.curLeftHipHeight ):

            x1, y1 = self.curLeftElbowWidth, self.curLeftElbowHeight
            x2, y2 = self.curLeftWristWidth, self.curLeftWristHeight


            x3, y3 = self.curRightElbowWidth, self.curRightElbowHeight
            x4, y4 = self.curRightWristWidth, self.curRightWristHeight

            x5, y5 = self.curSpineWidth, self.curSpineHeight

            #compare the two slopes to make sure right arm is completely straight
            rightElbowWristSlope = (y4 -y3)//(x4 - x3)

            rightElbowShoulderSlope = (y3 - y5)//(x3 - x5)

            if self.percentDifference(rightElbowWristSlope, rightElbowShoulderSlope) > 10:
                firstError = 10
                self.moveAccuracies['hiphop'] = 'Make sure your right arm is completely straight in hiphop.'
            else:
                firstError = 0
                self.moveAccuracies['hiphop'] = 'Your right arm is looking great in hiphop!'


            #left arm slopes should have the same magnitude, but opposite sign
            leftElbowWristSlope = (y2 - y1)//(x2 - x1)
            leftElbowShoulderSlope = (y5 - y1)//(x5 - x1)

            if (self.percentDifference(abs(leftElbowWristSlope), leftElbowShoulderSlope) > 10
                and leftElbowWristSlope > 0):
                secondError = 7
                self.moveAccuracies['hiphop'] = 'Your left elbow should be lower in hiphop.'
            else:
                secondError = 0
                self.moveAccuracies['hiphop'] = 'Your arms are at the perfect positions for hiphop!'

            avgError = (firstError + secondError)//2
        else:
            avgError = 25
            self.moveAccuracies['hiphop'] = 'You need to keep your arms higher during hiphop!'

        return avgError


    def getScore(self):

        # converts the error range into a score range based upon chosen level

        if self.error != None:

            if self.level == 'easy':

                if self.error <= 7:
                    self.score += 25
                elif self.error <= 15:
                    self.score += 10
                else:
                    self.score += 3

            elif self.level == 'difficult':

                if self.error <= 3:
                    self.score += 25
                elif self.error <= 7:
                    self.score += 10
                else:
                    self.score += 3 

        self.error = None


    def getMove(self, index):
        moves = self.movesList
        return moves[index]


    def run(self):
        
        pygame.time.set_timer(self.switch_image_event, self.timePerMove)
        pygame.time.set_timer(self.add_subscore_event, self.increment_subscore)
        global musicRunning

        playGameMusic(self.song).play()

        # -------- Main Program Loop -----------
        while not self._done:

            # --- Main event loop
            for event in pygame.event.get(): # User did something

                if event.type == pygame.QUIT: # If user clicked close
                    
                    musicRunning = False
                    self._done = True # Flag that we are done so we exit this loop
                    self.displayEndScreen()
                    

                elif event.type == pygame.VIDEORESIZE: # window resized
                    self._screen = pygame.display.set_mode(event.dict['size'], 
                                               pygame.HWSURFACE|pygame.DOUBLEBUF|pygame.RESIZABLE, 32)
                

                elif event.type == self.switch_image_event:
                    
                    if self.moveCount < len(self.movesList) - 1:
                        self.moveCount += 1
                    else:
                        self._done = True
                        self._kinect.close()
                        musicRunning = False
                        self.displayEndScreen()
                        self.pauseUntilKeypressed()
                        

                    index = self.moveCount
                    moveType = self.getMove(index)
                    
                    if moveType == 'goalpost':
                        currError = self.getGoalpostError()
                    elif moveType == 'disco':
                        currError = self.getDiscoError()
                    elif moveType == 'dab':
                        currError = self.getDabError()
                    elif moveType == 'hiphop':
                        currError = self.getHipHopError()
                    # elif moveType == 'crouch':
                    #     currError = self.crouchError()

                    self.error = currError
                    self.currMoveType = moveType

                elif event.type == self.add_subscore_event:
                    self.score += self.subscore
                    
            # --- Game logic should go here

            # --- Getting frames and drawing  
            # --- Woohoo! We've got a color frame! Let's fill out back buffer surface with frame's data 
            if self._kinect.has_new_color_frame():
                frame = self._kinect.get_last_color_frame()
                self.draw_color_frame(frame, self._frame_surface)
                frame = None

            # --- Cool! We have a body frame, so can get skeletons
            if self._kinect.has_new_body_frame(): 
                self._bodies = self._kinect.get_last_body_frame()

            # --- draw skeletons to _frame_surface
            if self._bodies is not None: 
                for i in range(0, self._kinect.max_body_count):
                    body = self._bodies.bodies[i]
                    if not body.is_tracked: 
                        continue 
                    
                    joints = body.joints 
                    # convert joint coordinates to color space 
                    joint_points = self._kinect.body_joints_to_color_space(joints)
                    self.draw_body(joints, joint_points, SKELETON_COLORS[i])

                    #get right wrist x and y pos
                    if joints[PyKinectV2.JointType_WristRight].TrackingState != PyKinectV2.TrackingState_NotTracked:
                        self.curRightWristHeight = joints[PyKinectV2.JointType_WristRight].Position.y
                        self.curRightWristWidth = joints[PyKinectV2.JointType_WristRight].Position.x

                    #get left wrist x and y pos
                    if joints[PyKinectV2.JointType_WristLeft].TrackingState != PyKinectV2.TrackingState_NotTracked:
                        self.curLeftWristHeight = joints[PyKinectV2.JointType_WristLeft].Position.y
                        self.curLeftWristWidth = joints[PyKinectV2.JointType_WristLeft].Position.x
                        
                    #get right elbow x and y pos
                    if joints[PyKinectV2.JointType_ElbowRight].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curRightElbowHeight = joints[PyKinectV2.JointType_ElbowRight].Position.y 
                        self.curRightElbowWidth = joints[PyKinectV2.JointType_ElbowRight].Position.x

                    #get left elbow x and y pos
                    if joints[PyKinectV2.JointType_ElbowLeft].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curLeftElbowHeight = joints[PyKinectV2.JointType_ElbowLeft].Position.y 
                        self.curLeftElbowWidth = joints[PyKinectV2.JointType_ElbowLeft].Position.x

                    
                    if joints[PyKinectV2.JointType_SpineShoulder].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curSpineHeight = joints[PyKinectV2.JointType_SpineShoulder].Position.y 
                        self.curSpineWidth = joints[PyKinectV2.JointType_SpineShoulder].Position.x

                    if joints[PyKinectV2.JointType_Head].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curHeadHeight = joints[PyKinectV2.JointType_Head].Position.y 
                        self.curHeadWidth = joints[PyKinectV2.JointType_Head].Position.x

                    if joints[PyKinectV2.JointType_Neck].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curNeckHeight = joints[PyKinectV2.JointType_Neck].Position.y 
                        self.curNeckWidth = joints[PyKinectV2.JointType_Neck].Position.x

                    if joints[PyKinectV2.JointType_HipRight].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curRightHipHeight = joints[PyKinectV2.JointType_HipRight].Position.y 
                        self.curRightHipWidth = joints[PyKinectV2.JointType_HipRight].Position.x

                    if joints[PyKinectV2.JointType_HipLeft].TrackingState != PyKinectV2.TrackingState_NotTracked: 
                        self.curLeftHipHeight = joints[PyKinectV2.JointType_HipLeft].Position.y 
                        self.curLeftHipWidth = joints[PyKinectV2.JointType_HipLeft].Position.x


                    index = self.moveCount
                    moveType = self.getMove(index)

                    if moveType == 'goalpost':
                        currError = self.getGoalpostError()
                    elif moveType == 'disco':
                        currError = self.getDiscoError()
                    elif moveType == 'dab':
                        currError = self.getDabError()
                    elif moveType == 'hiphop':
                        currError = self.getHipHopError()
                    
                    # don't want to call getScore() because this creates the final score
                    # instead we increment little by little to see if player is moving toward the correct position
                    
                    self.subscore = 0
                    if currError < 10:
                        self.subscore = 2
                    elif currError < 25:
                        self.subscore = 0.5
                    

                    self.prevRightWristHeight = self.curRightWristHeight
                    self.prevRightWristWidth = self.curRightWristWidth

                    self.prevLeftWristHeight = self.curLeftWristHeight
                    self.prevLeftWristWidth = self.curLeftWristWidth

                    self.prevRightElbowHeight = self.curRightElbowHeight
                    self.prevRightElbowWidth = self.curRightElbowWidth

                    self.prevLeftElbowHeight = self.curLeftElbowHeight
                    self.prevLeftElbowWidth = self.curLeftElbowWidth
                    
                    self.prevSpineHeight = self.curSpineHeight
                    self.prevSpineWidth = self.curSpineWidth

        
            # based upon magnitude of error, a score is assigned and incremented
            self.getScore()
            
            # --- copy back buffer surface pixels to the screen, resize it if needed and keep aspect ratio
            # --- (screen size may be different from Kinect's color frame size) 

            # renders the score text onto screen so player can see it while playing
            scoreFont = pygame.font.SysFont("courier new", 40, bold=True)
            scoreText = scoreFont.render(f'Current Score: {self.score}', True, self.black)
            scoreWidth = (5/6) * (self._frame_surface.get_width())
            scoreHeight = (1/6) * (self._frame_surface.get_height())
            textBlock = scoreText.get_rect()
            textBlock.center = (scoreWidth, scoreHeight)
            self._frame_surface.blit(scoreText, textBlock)
            
            #while an image is displayed, it moves across the screen during the time interval in which
            #the player should move towards that position
            if self.moveCount != self.prevIndex:
                self.imageDx = 0
                self.prevIndex = self.moveCount

            frameShift = 10
            self.imageDx -= frameShift
            
            currDx = self.imageDx
            currMov = self.getMove(self.moveCount)
            self.displayMoveImage(currMov, currDx)

            h_to_w = float(self._frame_surface.get_height()) / self._frame_surface.get_width()
            target_height = int(h_to_w * self._screen.get_width())
            surface_to_draw = pygame.transform.scale(self._frame_surface, (self._screen.get_width(), target_height));
            self._screen.blit(surface_to_draw, (0,0))
            surface_to_draw = None
            pygame.display.update()

            # --- Go ahead and update the screen with what we've drawn.
            pygame.display.flip()

            # --- Limit to 60 frames per second
            self._clock.tick(60)

        # Close our Kinect sensor, close the window and quit.

        self._kinect.close()
        self.displayEndScreen()
        pygame.quit()


__main__ = "Real Time Dance Motion"
game = RunJustDance();
game.displayStartScreen();
game.displayLevelScreen();
game.displayEndScreen();