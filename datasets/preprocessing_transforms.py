"""
Functions used to process and augment video data prior to passing into a model to train. 
Additionally also processing all bounding boxes in a video according to the transformations performed on the video.

Usage:
    In a custom dataset class:
    from preprocessing_transforms import *

clip: Input to __call__ of each transform is a list of PIL images
"""

import torch
from torchvision.transforms import functional as F
from PIL import Image
from PIL import ImageChops
import numpy as np
from abc import ABCMeta

class PreprocTransform(object):
    """
    Abstract class for preprocessing transforms that contains methods to convert clips to PIL images.
    """
    __metaclass__ = ABCMeta
    def __init__(self, **kwargs):
        self.numpy_type = type(np.array(0))

    def _format_clip(self, clip):

        assert((type(clip)==type(list())) or (type(clip)==self.numpy_type)), "Clips input to preprocessing transforms must be a list of PIL Images or numpy arrays"
        output_clip = []
        
        if type(clip[0]) == self.numpy_type:
            for frame in clip:
                if len(frame.size)==3:
                    output_clip.append(Image.fromarray(frame, mode='F'))
                else:
                    import pdb; pdb.set_trace()
                    output_clip.append(Image.fromarray(frame))
        else:
            output_clip = clip


        return output_clip
    
    def _format_clip_numpy(self, clip):
        assert(type(clip)==type(list())), "Clip must be a list when input to _format_clip_numpy"
        output_clip = []
        if type(clip[0]) == self.numpy_type:
            output_clip = clip

        else:
            for frame in clip:
                output_clip.append(np.array(frame))

        return np.array(output_clip)





class ResizeClip(PreprocTransform):
    def __init__(self, size_h, size_w, *args, **kwargs):
        super(ResizeClip, self).__init__(*args, **kwargs)

        self.size_h = size_h
        self.size_w = size_w
        
    def __call__(self, clip, bbox=[]):

        clip = self._format_clip(clip)
        out_clip = []
        out_bbox = []
        for frame_ind in range(len(clip)):
            frame = clip[frame_ind]

            proc_frame = frame.resize((self.size_w, self.size_h))
            out_clip.append(proc_frame)
            if bbox!=[]:
                temp_bbox = np.zeros(bbox[frame_ind].shape) 
                for class_ind in range(len(bbox)):
                    xmin, ymin, xmax, ymax = bbox[frame_ind, class_ind]
                    proc_bbox = resize_bbox(xmin, ymin, xmax, ymax, frame.size, (self.size_w, self.size_h))
                    temp_bbox[class_ind,:] = proc_bbox
                out_bbox.append(temp_bbox)

        if bbox!=[]:
            return out_clip, np.array(out_bbox)
        else:
            return out_clip


class CropClip(PreprocTransform):
    def __init__(self, xmin, xmax, ymin, ymax, *args, **kwargs):
        super(CropClip, self).__init__(*args, **kwargs)
        self.bbox_xmin = xmin
        self.bbox_xmax = xmax
        self.bbox_ymin = ymin
        self.bbox_ymax = ymax


    def _update_bbox(self, xmin, xmax, ymin, ymax):
        self.bbox_xmin = xmin
        self.bbox_xmax = xmax
        self.bbox_ymin = ymin
        self.bbox_ymax = ymax

        
    def __call__(self, clip, bbox=[]):
        clip = self._format_clip(clip)
        out_clip = []
        out_bbox = []

        for frame_ind in range(len(clip)):
            frame = clip[frame_ind]
            proc_frame = frame.crop((self.bbox_xmin, self.bbox_ymin, self.bbox_xmax, self.bbox_ymax))
            out_clip.append(proc_frame)

            if bbox!=[]:
                temp_bbox = np.zeros(bbox[frame_ind].shape) 
                for class_ind in range(len(bbox)):
                    xmin, ymin, xmax, ymax = bbox[frame_ind, class_ind]
                    proc_bbox = crop_bbox(xmin, ymin, xmax, ymax, self.bbox_xmin, self.bbox_xmax, self.bbox_ymin, self.bbox_ymax)
                    temp_bbox[class_ind,:] = proc_bbox
                out_bbox.append(temp_bbox)

        if bbox!=[]:
            return out_clip, np.array(out_bbox)
        else:
            return out_clip


class RandomCropClip(PreprocTransform):
    def __init__(self, crop_w, crop_h, *args, **kwargs):
        super(RandomCropClip, self).__init__(*args, **kwargs)
        self.crop_w = crop_w 
        self.crop_h = crop_h

        self.crop_transform = CropClip(0, 0, self.crop_w, self.crop_h)

        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None


    def _update_random_sample(self, frame_w, frame_h):
        self.xmin = np.random.randint(0, frame_w-self.crop_w)
        self.xmax = self.xmin + self.crop_w
        self.ymin = np.random.randint(0, frame_h-self.crop_h)
        self.ymax = self.ymin + self.crop_h

    def get_random_sample(self):
        return self.xmin, self.xmax, self.ymin, self.ymax
        
    def __call__(self, clip, bbox=[]):
        clip = self._format_clip(clip)
        frame_shape = clip[0].size
        self._update_random_sample(frame_shape[0], frame_shape[1])
        self.crop_transform._update_bbox(self.xmin, self.xmax, self.ymin, self.ymax) 
        return self.crop_transform(clip, bbox)


class CenterCropClip(PreprocTransform):
    def __init__(self, crop_w, crop_h, *args, **kwargs):
        super(CenterCropClip, self).__init__(*args, **kwargs)
        self.crop_w = crop_w 
        self.crop_h = crop_h

        self.crop_transform = CropClip(0, 0, self.crop_w, self.crop_h)

    def _calculate_center(self, frame_w, frame_h):
        xmin = int(frame_w/2 - self.crop_w/2)
        xmax = int(frame_w/2 + self.crop_w/2)
        ymin = int(frame_h/2 - self.crop_h/2)
        ymax = int(frame_h/2 + self.crop_h/2)
        return xmin, xmax, ymin, ymax
        
    def __call__(self, clip, bbox=[]):
        clip = self._format_clip(clip)
        frame_shape = clip[0].size
        xmin, xmax, ymin, ymax = self._calculate_center(frame_shape[0], frame_shape[1])
        self.crop_transform._update_bbox(xmin, xmax, ymin, ymax) 
        return self.crop_transform(clip, bbox)


class RandomFlipClip(PreprocTransform):
    """
    Specify a flip direction:
    Horizontal, left right flip = 'h' (Default)
    Vertical, top bottom flip = 'v'
    """
    def __init__(self, direction='h', p=0.5, *args, **kwargs):
        super(RandomFlipClip, self).__init__(*args, **kwargs)
        self.direction = direction
        self.p = p
            
    def _random_flip(self):
        flip_prob = np.random.random()
        if flip_prob >= self.p:
            return 0
        else:
            return 1

    def _h_flip(self, bbox, frame_size):
        bbox_shape = bbox.shape
        output_bbox = np.zeros(bbox_shape)
        for bbox_ind in range(bbox_shape[0]):
            xmin, ymin, xmax, ymax = bbox[bbox_ind] 
            width = frame_size[1]
            xmax_new = width - xmin 
            xmin_new = width - xmax
            output_bbox[bbox_ind] = xmin_new, ymin, xmax_new, ymax
        return output_bbox 

    def _v_flip(self, bbox, frame_size):
        bbox_shape = bbox.shape
        output_bbox = np.zeros(bbox_shape)
        for bbox_ind in range(bbox_shape[0]):
            xmin, ymin, xmax, ymax = bbox[bbox_ind] 
            height = frame_size[0]
            ymax_new = height - ymin 
            ymin_new = height - ymax
            output_bbox[bbox_ind] = xmin_new, ymin, xmax_new, ymax
        return output_bbox 


    def _flip_data(self, clip, bbox=[]):
        output_bbox = []
        
        if self.direction == 'h':
            output_clip = [frame.transpose(Image.FLIP_LEFT_RIGHT) for frame in clip]
            
            if bbox!=[]:
                output_bbox = [self._h_flip(curr_bbox, output_clip[0].size) for curr_bbox in bbox] 

        elif self.direction == 'v':
            output_clip = [frame.transpose(Image.FLIP_TOP_BOTTOM) for frame in clip]

            if bbox!=[]:
                output_bbox = [self._v_flip(curr_bbox, output_clip[0].size) for curr_bbox in bbox]

        return output_clip, output_bbox 
        

    def __call__(self, clip, bbox=[]):
        clip = self._format_clip(clip)
        flip = self._random_flip()
        out_clip = clip
        out_bbox = bbox
        if flip:
            out_clip, out_bbox = self._flip_data(clip, bbox)

        if bbox!=[]:
            return out_clip, out_bbox
        else:
            return out_clip

class ToTensorClip(PreprocTransform):
    """
    Convert a list of PIL images or numpy arrays to a 5 dimensional pytorch tensor [batch, frame, channel, height, width]
    """
    def __init__(self, *args, **kwargs):
        super(ToTensorClip, self).__init__(*args, **kwargs)

    def __call__(self, clip, bbox=[]):
        clip = self._format_clip_numpy(clip)
        clip = torch.from_numpy(clip).float()
        if bbox!=[]:
            bbox = torch.from_numpy(np.array(bbox))
            return clip, bbox
        else:
            return clip
        

class RandomRotateClip(PreprocTransform):
    """
    Randomly rotate a clip from a fixed set of angles.
    """
    def __init__(self,  angles=[0,90,180,270], *args, **kwargs):
        super(RandomRotateClip, self).__init__(*args, **kwargs)
        self.angles = angles

    ######
    # Code from: https://stackoverflow.com/questions/20924085/python-conversion-between-coordinates
    def _cart2pol(self, point):
        x,y = point
        rho = np.sqrt(x**2 + y**2)
        phi = np.arctan2(y, x)
        return(rho, phi)
    
    def _pol2cart(self, point):
        rho, phi = point
        x = rho * np.cos(phi)
        y = rho * np.sin(phi)
        return(x, y)
    #####


    def _rotate_bbox(self, bboxes, frame_shape, angle):
        angle = np.deg2rad(angle)
        bboxes_shape = bboxes.shape
        output_bboxes = np.zeros(bboxes_shape)
        frame_h, frame_w = frame_shape 
        half_h = frame_h/2. 
        half_w = frame_w/2. 

        for bbox_ind in range(bboxes_shape[0]):
            xmin, ymin, xmax, ymax = bboxes[bbox_ind]
            tl = (xmin-half_w, ymax-half_h)
            tr = (xmax-half_w, ymax-half_h)
            bl = (xmin-half_w, ymin-half_h)
            br = (xmax-half_w, ymin-half_h)

            tl = self._cart2pol(tl) 
            tr = self._cart2pol(tr)    
            bl = self._cart2pol(bl)
            br = self._cart2pol(br)

            tl = (tl[0], tl[1] + angle)
            tr = (tr[0], tr[1] + angle)
            bl = (bl[0], bl[1] + angle)
            br = (br[0], br[1] + angle)

            tl = self._pol2cart(tl) 
            tr = self._pol2cart(tr)    
            bl = self._pol2cart(bl)
            br = self._pol2cart(br)

            tl = (tl[0]+half_w, tl[1]+half_h)
            tr = (tr[0]+half_w, tr[1]+half_h)
            bl = (bl[0]+half_w, bl[1]+half_h)
            br = (br[0]+half_w, br[1]+half_h)

            xmin_new = int(min(tl[0], tr[0], bl[0], br[0]))
            xmax_new = int(max(tl[0], tr[0], bl[0], br[0]))
            ymin_new = int(min(tl[1], tr[1], bl[1], br[1]))
            ymax_new = int(max(tl[1], tr[1], bl[1], br[1]))

            output_bboxes[bbox_ind] = [xmin_new, ymin_new, xmax_new, ymax_new]

        return output_bboxes



    def __call__(self, clip, bbox=[]):
        angle = np.random.choice(self.angles)
        output_clip = []
        for frame in clip:
            output_clip.append(frame.rotate(angle))

        if bbox!=[]:
            bbox = np.array(bbox)
            output_bboxes = np.zeros(bbox.shape)
            for bbox_ind in range(bbox.shape[0]):
                output_bboxes[bbox_ind] = self._rotate_bbox(bbox[bbox_ind], clip[0].size, angle)

            return output_clip, output_bboxes 

        return output_clip



#class oversample(object):
#    def __init__(self, output_size):
#        self.size_h, self.size_w = output_size
#        
#    def __call__(self, clip, bbox):
#        return clip, bbox


class SubtractMeanClip(PreprocTransform):
    def __init__(self, **kwargs):
        super(SubtractMeanClip, self).__init__(**kwargs)
        self.clip_mean_args = kwargs['clip_mean']
        self.clip_mean_1    = []
        self.clip_mean_2    = []
        self.clip_mean_3    = []

        for frame in self.clip_mean_args:
            self.clip_mean_1.append(Image.fromarray(frame[:, : ,0], mode='F'))
            self.clip_mean_2.append(Image.fromarray(frame[:, : ,1], mode='F'))
            self.clip_mean_3.append(Image.fromarray(frame[:, : ,2], mode='F'))
        import pdb; pdb.set_trace()

        
    def __call__(self, clip, bbox=[]):
        print(len(clip))
        for clip_ind in range(len(clip)):
            clip[clip_ind][:,:,0] = ImageChops.subtract(clip[clip_ind][:,:,0], self.clip_mean_1[clip_ind])
            clip[clip_ind][:,:,1] = ImageChops.subtract(clip[clip_ind][:,:,1], self.clip_mean_2[clip_ind])
            clip[clip_ind][:,:,2] = ImageChops.subtract(clip[clip_ind][:,:,2], self.clip_mean_3[clip_ind])
            #clip[clip_ind] = clip[clip_ind].sub(self.clip_mean[clip_ind])

        
        if bbox!=[]:
            return clip, bbox

        else:
            return clip


class ApplyToClip(PreprocTransform):
    def __init__(self, **kwargs):
        super(ApplyToClip, self).__init__(**kwargs)
        self.transform = kwargs['transform']

    def __call__(self, clip, bbox=[]):
        output_clip = []
        for frame in clip:
            output_clip.append(self.transform(frame))

        if bbox!=[]:
            return output_clip, bbox

        else:
            return output_clip




def resize_bbox(xmin, xmax, ymin, ymax, img_shape, resize_shape):
    # Resize a bounding box within a frame relative to the amount that the frame was resized

    img_h = img_shape[0]
    img_w = img_shape[1]

    res_h = resize_shape[0]
    res_w = resize_shape[1]

    frac_h = res_h/float(img_h)
    frac_w = res_w/float(img_w)

    xmin_new = int(xmin * frac_w)
    xmax_new = int(xmax * frac_w)

    ymin_new = int(ymin * frac_h)
    ymax_new = int(ymax * frac_h)

    return xmin_new, xmax_new, ymin_new, ymax_new 


def crop_bbox(xmin, xmax, ymin, ymax, crop_xmin, crop_xmax, crop_ymin, crop_ymax):
    if (xmin >= crop_xmax) or (xmax <= crop_xmin) or (ymin >= crop_ymax) or (ymax <= crop_ymin):
        return -1, -1, -1, -1

    if ymax > crop_ymax:
        ymax_new = crop_ymax
    else:
        ymax_new = ymax

    if xmax > crop_xmax:
        xmax_new = crop_xmax
    else:
        xmax_new = xmax
    
    if ymin < crop_ymin:
        ymin_new = crop_ymin
    else:
        ymin_new = ymin 

    if xmin < crop_xmin:
        xmin_new = crop_xmin
    else:
        xmin_new = xmin 

    return xmin_new, xmax_new, ymin_new, ymax_new


