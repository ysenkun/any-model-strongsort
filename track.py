import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from strong_sort.utils.parser import get_config
from strong_sort.strong_sort import StrongSORT

class main:
    def __init__(self):
        #opencv model for face detection
        self.face_cascade_path = 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + self.face_cascade_path)

        self.save_vid = True 
        self.font_style = 'fonts-japanese-mincho.ttf'

        # initialize StrongSORT
        self.cfg = get_config()
        self.cfg.merge_from_file('strong_sort/configs/strong_sort.yaml')
        self.strong_sort_weights = 'strong_sort/deep/checkpoint/osnet_x0_25_market1501.pth'
        self.device = 'cpu'

        self.strongsort = StrongSORT(
            self.strong_sort_weights,
            self.device,
            max_dist=self.cfg.STRONGSORT.MAX_DIST,
            max_iou_distance=self.cfg.STRONGSORT.MAX_IOU_DISTANCE,
            max_age=self.cfg.STRONGSORT.MAX_AGE,
            n_init=self.cfg.STRONGSORT.N_INIT,
            nn_budget=self.cfg.STRONGSORT.NN_BUDGET,
            mc_lambda=self.cfg.STRONGSORT.MC_LAMBDA,
            ema_alpha=self.cfg.STRONGSORT.EMA_ALPHA,
        )
        
    def video(self):
        cap = cv2.VideoCapture("input.mp4")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        fmt = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
        writer = cv2.VideoWriter('result.mp4',
                                 fmt, fps, (width, height))
        tframe = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        num = 0
        while True:
            print('frame count ' + str(num) + '/' + str(tframe))
            num += 1

            ret, frame = cap.read()
            if not ret:
                break

            outputs,confs = main.any_model(self,frame)
            
            if len(outputs) > 0:
                for j, (output, conf) in enumerate(zip(outputs, confs)):
                        frame = main.annotation(self, frame, output, conf)
            #save
            if self.save_vid:
                writer.write(frame)
            
        cap.release()
        writer.release()
        cv2.destroyAllWindows()

    def any_model(self,frame):
        src_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(src_gray)
        outputs = []
        confs = []

        #Change annotation coordinates for StrongSORT
        #From [x_topleft, y_topleft, width, height] to [x_center, y_center, width, height]
        if faces is not None and len(faces):
            x = torch.tensor(faces)
            
            xywhs = x.clone() if isinstance(x, torch.Tensor) else np.copy(x)
            xywhs[:, 0] = (x[:, 0] + x[:, 2]/2) # x center
            xywhs[:, 1] = (x[:, 1] + x[:, 3]/2) # y center
            
            #Static confs(accuracy) and clss(class) because opencv face detection is used
            confs = torch.tensor([0.9 for i in range(len(faces))])
            clss = torch.tensor([0 for i in range(len(faces))])

            #Run StorngSORT
            outputs = self.strongsort.update(xywhs.cpu(), confs.cpu(), clss.cpu(), frame)
            
        return outputs,confs

    def annotation(self, frame, output, conf):
        bboxes = output[0:4]
        id = int(output[4])
        clss = int(output[5])
        label = None #Make the object name change to match the clss number

        frame = frame if isinstance(frame, Image.Image) else Image.fromarray(frame)
        draw = ImageDraw.Draw(frame)
        rectcolor = (0, 188, 68)
        linewidth = 8
        draw.rectangle([(output[0], output[1]), (output[2], output[3])],
                       outline=rectcolor, width=linewidth)

        textcolor = (255, 255, 255)
        textsize = 40

        #Specify font style by path
        font = ImageFont.truetype(self.font_style, textsize)

        text = f'{id} {label} {conf:.2f}'

        txpos = (output[0], output[1]-textsize-linewidth//2) #Coordinates to start drawing text
        txw, txh = draw.textsize(text, font=font)

        draw.rectangle([txpos, (output[0]+txw, output[1])], outline=rectcolor,
                       fill=rectcolor, width=linewidth)

        draw.text(txpos, text, font=font, fill=textcolor)
        frame = np.asarray(frame)

        return frame

if __name__ == '__main__':
    run = main()
    run.video()