# -*- coding: utf-8 -*-
"""Utilities to load a custom version of the VIST dataset"""


import os
import re
import random
from PIL import Image

import torch
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torch.utils.data as data

from .datadirectory import data_directory
from .labels import Annotations


IMG_EXTENSIONS = [
    '.jpg', '.JPG', '.jpeg', '.JPEG',
    '.png', '.PNG', '.ppm', '.PPM', '.bmp', '.BMP',
]


def is_image_file(filename):
    return any(filename.endswith(extension) for extension in IMG_EXTENSIONS)

def _vector_to_tensor(vec):
    return torch.from_numpy(vec)

def _vectors_to_tensor(vectors, tensor_size_min, tensor_size_max):
    tensors = list(map(_vector_to_tensor, vectors))
    if len(tensors) < tensor_size_min or len(tensors) > tensor_size_max:
        return False
    return torch.stack(tensors)


def sentence_to_tensor(sentence, word2vec, tensor_size_min, tensor_size_max):
    text = _vectors_to_tensor(word2vec.sentence_embedding(
        sentence), tensor_size_min, tensor_size_max)
    if not torch.is_tensor(text):
        return False, 0

    if text.size()[0] >= tensor_size_max:
        # note the -1 handles the 0 indices
        return text, tensor_size_max - 1
    text_size = text.size()[0]
    texts_padded = torch.cat([text,
                              torch.zeros(tensor_size_max - text_size, 300)
                             ])
    return texts_padded, text_size - 1


_REGEXP_ID = re.compile(r'^(.+)\.\D+$', re.IGNORECASE)


def _img_path_to_text(filename, annotations):
    results = _REGEXP_ID.match(filename)
    if results is None:
        return False

    groups = results.groups()
    if len(groups) != 1:
        return False

    return annotations[groups[0]] if groups[0] in annotations else False



def default_loader(path):
    return Image.open(path).convert('RGB')


def check_path(path):
    try:
        img = default_loader(path)
    except:
        return path

    tensor = transforms.ToTensor()(img)
    if tensor.size()[1] != 224 or tensor.size()[2] != 224:
        return path
    return False

# i_path = os.path.join(data_directory, 'train')
def find_bad_images(root_path):
    """In the target path, return a list of all images not valid for processing"""
    ps = [os.path.join(root_path, path) for path in os.listdir(root_path)]
    ps_invalid = [check_path(path) for path in ps]
    ps_invalid_paths = [path for path in ps_invalid if path is not False]

    return ps_invalid_paths

# find_bad_images(os.path.join(data_directory, 'train'))
# find_bad_images(os.path.join(data_directory, 'test'))

class ImageLoader(data.Dataset):

    def __init__(self,
                 group,
                 word2vec,
                 mismatched_passes=3,
                 max_tokens=15,
                 seed=451,
                 transform=None,
                 target_transform=None,
                 loader=default_loader):

        self.transform = transform
        self.target_transform = target_transform
        self.loader = loader

        self._mismatched_passes = mismatched_passes
        self._seed = seed

        self._image_path = os.path.join(data_directory, group)

        annotations = Annotations.annotations_train() if \
            group == 'train' else Annotations.annotations_test()
        texts = [(d, _img_path_to_text(d, annotations))
                 for d in os.listdir(self._image_path)]
        texts_clean = [(d, text) for d, text in texts if text != False]

        text_tensors = [(d, sentence_to_tensor(text, word2vec, 1, max_tokens))
                        for d, text in texts_clean if text != False]
        text_tensors_clean = [(d, tensor, text_size) for d, (tensor, text_size) in text_tensors if
                              torch.is_tensor(tensor)]

        self._valid_values = text_tensors_clean

    def __getitem__(self, index):
        idx = index % len(self._valid_values)

        filename, text, text_size = self._valid_values[idx]
        path = os.path.join(self._image_path, filename)
        img = self.loader(path)
        if self.transform is not None:
            img = self.transform(img)

        # test if this is a mismatch pass
        real_pass = index // len(self._valid_values) == idx % self._mismatched_passes
        if not real_pass:
            random.seed(self._seed + index)
            idx_different = (random.randint(0,
                                            len(self._valid_values) - 1) + idx) % len(self._valid_values)
            _, text, text_size = self._valid_values[idx_different]

        target = torch.Tensor([1 if real_pass else -1])

        if self.target_transform is not None:
            target = self.target_transform(target)

        if img.size()[1] != 224 or img.size()[2] != 224:
            raise(RuntimeError("Invalid image size at " + filename + "\n"))

        return img, text, text_size, target

    def __len__(self):
        return len(self._valid_values) * self._mismatched_passes
