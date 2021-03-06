from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

VGG16_NPY_PATH = 'vgg16.npy'
K = 10
WD = 5e-4

data_dict = np.load(VGG16_NPY_PATH, encoding='latin1').item()
x_ = tf.placeholder(tf.float32, shape=[1, None, None, 3])
y_ = tf.placeholder(tf.float32, shape=[1, None, None, K])
is_training_ = tf.placeholder(tf.bool, name='is_training')


def activation_summary(var):
    tensor_name = var.op.name
    tf.summary.histogram(tensor_name + '/activations', var)
    tf.summary.scalar(tensor_name + '/sparsity', tf.nn.zero_fraction(var))


def variable_summaries(var):
    if not tf.get_variable_scope().reuse:
        name = var.op.name
        with tf.name_scope('summaries'):
            mean = tf.reduce_mean(var)
            tf.summary.scalar(name + '/mean', mean)
            with tf.name_scope('stddev'):
                stddev = tf.sqrt(tf.reduce_sum(tf.square(var - mean)))
            tf.summary.scalar(name + '/sttdev', stddev)
            tf.summary.scalar(name + '/max', tf.reduce_max(var))
            tf.summary.scalar(name + '/min', tf.reduce_min(var))
            tf.summary.histogram(name, var)


def get_conv_filter(name):
    init = tf.constant_initializer(value=data_dict[name][0],
                                   dtype=tf.float32)
    shape = data_dict[name][0].shape
    var = tf.get_variable(name="weight", initializer=init, shape=shape)
    if not tf.get_variable_scope().reuse:
        weight_decay = tf.multiply(tf.nn.l2_loss(var), WD, name='weight_loss')
        tf.add_to_collection('losses', weight_decay)
    variable_summaries(var)
    return var


def get_deconv_filter(f_shape):
    width = f_shape[0]
    heigh = f_shape[0]
    f = ceil(width / 2.0)
    c = (2 * f - 1 - f % 2) / (2.0 * f)
    bilinear = np.zeros([f_shape[0], f_shape[1]])
    for x in range(width):
        for y in range(heigh):
            value = (1 - abs(x / f - c)) * (1 - abs(y / f - c))
            bilinear[x, y] = value
    weights = np.zeros(f_shape)
    for i in range(f_shape[2]):
        weights[:, :, i, i] = bilinear

    init = tf.constant_initializer(value=weights,
                                   dtype=tf.float32)
    var = tf.get_variable(name="up_filter", initializer=init,
                          shape=weights.shape)
    return var


def get_bias(name):
    bias_wights = data_dict[name][1]
    shape = data_dict[name][1].shape
    init = tf.constant_initializer(value=bias_wights,
                                   dtype=tf.float32)
    var = tf.get_variable(name="biases", initializer=init, shape=shape)
    variable_summaries(var)
    return var


def get_deconv_bias(shape):
    init = tf.constant(0.1, shape=shape)
    var = tf.get_variable(name="biases", initializer=init, shape=shape)
    variable_summaries(var)
    return var


def conv2d(bottom, weight):
    return tf.nn.conv2d(bottom, weight, strides=[1, 1, 1, 1], padding='SAME')


def batch_norm_layer(bottom, is_training, scope):
    return tf.contrib.layers.batch_norm(bottom,
                                        is_training=is_training,
                                        center=False,
                                        updates_collections=None,
                                        scope=scope+"_bn",
                                        reuse=(not is_training))


def conv_layer_with_bn(bottom, is_training, name=None):
    with tf.variable_scope(name) as scope:
        weight = get_conv_filter(name)
        bias = get_bias(name)
        conv = tf.nn.bias_add(conv2d(bottom, weight), bias)
        conv = tf.nn.relu(batch_norm_layer(conv, is_training, scope.name))
    activation_summary(conv)
    return conv


def deconv_layer_with_bn(bottom, shape, is_training, name=None):
    with tf.variable_scope(name) as scope:
        weight = get_deconv_filter(shape=shape)
        bias = get_deconv_bias(shape=shape[3])
        conv = tf.nn.bias_add(conv2d(bottom, weight), bias)
        conv = tf.nn.relu(batch_norm_layer(conv, is_training, scope.name))
    activation_summary(conv)
    return conv


def max_pool_with_argmax(bottom):
    with tf.name_scope('max_pool_arg_max'):
        _, indices = tf.nn.max_pool_with_argmax(
            bottom,
            ksize=[1, 2, 2, 1],
            strides=[1, 2, 2, 1],
            padding='SAME')
        indices = tf.stop_gradient(indices)
        bottom = tf.nn.max_pool(bottom,
                                ksize=[1, 2, 2, 1],
                                strides=[1, 2, 2, 1],
                                padding='SAME')
        return bottom, indices


def max_unpool_with_argmax(bottom, mask, output_shape=None):
    with tf.name_scope('max_unpool_with_argmax'):
        ksize = [1, 2, 2, 1]
        input_shape = bottom.get_shape().as_list()
        #  calculation new shape
        if output_shape is None:
            output_shape = (input_shape[0],
                            input_shape[1] * ksize[1],
                            input_shape[2] * ksize[2],
                            input_shape[3])
        # calculation indices for batch, height, width and feature maps
        one_like_mask = tf.ones_like(mask)
        batch_range = tf.reshape(tf.range(output_shape[0],
                                          dtype=tf.int64),
                                 shape=[input_shape[0], 1, 1, 1])
        b = one_like_mask * batch_range
        y = mask // (output_shape[2] * output_shape[3])
        x = mask % (output_shape[2] * output_shape[3]) // output_shape[3]
        feature_range = tf.range(output_shape[3], dtype=tf.int64)
        f = one_like_mask * feature_range
        # transpose indices & reshape update values to one dimension
        updates_size = tf.size(bottom)
        indices = tf.transpose(tf.reshape(tf.stack([b, y, x, f]), [4, updates_size]))
        values = tf.reshape(bottom, [updates_size])
        return tf.scatter_nd(indices, values, output_shape)


def get_model():
    conv1_1 = conv_layer_with_bn(x_, is_training_, "conv1_1")
    conv1_2 = conv_layer_with_bn(conv1_1, is_training_, "conv1_2")
    pool1, pool1_indices = max_pool_with_argmax(conv1_2, 'pool1')

    conv2_1 = conv_layer_with_bn(pool1, "conv2_1")
    conv2_2 = conv_layer_with_bn(conv2_1, "conv2_2")
    pool2, pool2_indices = max_pool_with_argmax(conv2_2, 'pool2')

    conv3_1 = conv_layer_with_bn(pool2, "conv3_1")
    conv3_2 = conv_layer_with_bn(conv3_1, "conv3_2")
    conv3_3 = conv_layer_with_bn(conv3_2, "conv3_3")
    pool3, pool3_indices = max_pool_with_argmax(conv3_3, 'pool3')

    conv4_1 = conv_layer_with_bn(pool3, "conv4_1")
    conv4_2 = conv_layer_with_bn(conv4_1, "conv4_2")
    conv4_3 = conv_layer_with_bn(conv4_2, "conv4_3")
    pool4, pool4_indices = max_pool_with_argmax(conv4_3, 'pool4')

    conv5_1 = conv_layer_with_bn(pool4, "conv5_1")
    conv5_2 = conv_layer_with_bn(conv5_1, "conv5_2")
    conv5_3 = conv_layer_with_bn(conv5_2, "conv5_3")
    pool5, pool5_indices = max_pool_with_argmax(conv5_3, 'pool5')

    # End of encoders
    # start of decoders

    up_sample_5 = max_unpool_with_argmax(pool5,
                                         pool5_indices,
                                         output_shape=tf.shape(conv5_3))
    up_conv5_1 = conv_layer_with_bn(up_sample_5, "up_conv5_1", shape=[3, 3, 512, 512])
    up_conv5_2 = conv_layer_with_bn(up_conv5_1, "up_conv5_2", shape=[3, 3, 512, 512])
    up_conv5_3 = conv_layer_with_bn(up_conv5_2, "up_conv5_3", shape=[3, 3, 512, 512])

    up_sample_4 = max_unpool_with_argmax(up_conv5_3,
                                         pool4_indices,
                                         output_shape=tf.shape(conv4_3))
    up_conv4_1 = conv_layer_with_bn(up_sample_4, "up_conv4_1", shape=[3, 3, 512, 512])
    up_conv4_2 = conv_layer_with_bn(up_conv4_1, "up_conv4_2", shape=[3, 3, 512, 512])
    up_conv4_3 = conv_layer_with_bn(up_conv4_2, "up_conv4_3", shape=[3, 3, 512, 512])

    up_sample_3 = max_unpool_with_argmax(up_conv4_3,
                                         pool3_indices,
                                         output_shape=tf.shape(conv3_3))
    up_conv3_1 = conv_layer_with_bn(up_sample_3, "up_conv3_1", shape=[3, 3, 512, 256])
    up_conv3_2 = conv_layer_with_bn(up_conv3_1, "up_conv3_2", shape=[3, 3, 256, 256])
    up_conv3_3 = conv_layer_with_bn(up_conv3_2, "up_conv3_3", shape=[3, 3, 256, 256])

    up_sample_2 = max_unpool_with_argmax(up_conv3_3,
                                         pool2_indices,
                                         output_shape=tf.shape(conv2_2))
    up_conv2_1 = conv_layer_with_bn(up_sample_2, "up_conv2_1", shape=[3, 3, 256, 128])
    up_conv2_2 = conv_layer_with_bn(up_conv2_1, "up_conv2_2", shape=[3, 3, 128, 128])

    up_sample_1 = max_unpool_with_argmax(up_conv2_2,
                                         pool1_indices,
                                         output_shape=tf.shape(conv1_2))
    up_conv1_1 = conv_layer_with_bn(up_sample_1, "up_conv1_1", shape=[3, 3, 128, 64])
    up_conv1_2 = conv_layer_with_bn(up_conv1_1, "up_conv1_2", shape=[3, 3, 64, K])

    return up_conv1_2
