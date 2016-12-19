"""A convolutional neural network for CIFAR-10 classification.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cifar
import tensorflow as tf


def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)


def bias_variable(shape):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial)


def conv2d(x, W):
    return tf.nn.conv2d(x, W, strides=[1, 1, 1, 1], padding='SAME')


def max_pool_2x2(x):
    return tf.nn.max_pool(x, ksize=[1, 2, 2, 1],
                          strides=[1, 2, 2, 1], padding='SAME')


def main(_):
    cifar10 = cifar.Cifar()
    cifar10.ReadDataSets(one_hot=True)

    keep_prob = tf.placeholder(tf.float32)

    # Create the model
    x = tf.placeholder(tf.float32, [None, 3072])

    # Define loss and optimizer
    y_ = tf.placeholder(tf.float32, [None, 10])

    x_image = tf.reshape(x, [-1, 32, 32, 3])

    # (32 - 3 + 2 * 1) / 1 +1 = 32
    W_conv1 = weight_variable([3, 3, 3, 32])
    b_conv1 = bias_variable([32])

    h_conv1 = tf.nn.relu(conv2d(x_image, W_conv1) + b_conv1)
    h_pool1 = max_pool_2x2(h_conv1)

    W_conv2 = weight_variable([3, 3, 32, 64])
    b_conv2 = bias_variable([64])

    h_conv2 = tf.nn.relu(conv2d(h_pool1, W_conv2) + b_conv2)
    h_pool2 = max_pool_2x2(h_conv2)

    W_conv3 = weight_variable([3, 3, 64, 128])
    b_conv3 = bias_variable([128])

    h_conv3 = tf.nn.relu(conv2d(h_pool2, W_conv3) + b_conv3)
    h_pool3 = max_pool_2x2(h_conv3)

    W_fc1 = weight_variable([4 * 4 * 128, 1024])
    b_fc1 = bias_variable([1024])

    h_pool3_flat = tf.reshape(h_pool3, [-1, 4 * 4 * 128])

    h_fc1 = tf.nn.relu(tf.matmul(h_pool3_flat, W_fc1) + b_fc1)
    #h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)

    W_fc2 = weight_variable([1024, 1024])
    b_fc2 = bias_variable([1024])

    h_fc2 = tf.nn.relu(tf.matmul(h_fc1, W_fc2) + b_fc2)
    #h_fc2_drop = tf.nn.dropout(h_fc2, keep_prob)

    W_fc3 = weight_variable([1024, 512])
    b_fc3 = bias_variable([512])

    h_fc3 = tf.nn.relu(tf.matmul(h_fc2, W_fc3) + b_fc3)
    #h_fc3_drop = tf.nn.dropout(h_fc3, keep_prob)

    W_fc4 = weight_variable([512, 10])
    b_fc4 = bias_variable([10])

    y_conv = tf.matmul(h_fc3, W_fc4) + b_fc4

    cross_entropy = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(y_conv, y_))
    train_step = tf.train.AdamOptimizer(1e-3).minimize(cross_entropy)
    correct_prediction = tf.equal(tf.argmax(y_conv, 1), tf.argmax(y_, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    sess = tf.InteractiveSession()
    sess.run(tf.global_variables_initializer())

    for i in range(20000):
        batch = cifar10.train.next_batch(200)
        if i % 100 == 0:
            train_accuracy = accuracy.eval(feed_dict={
                x: cifar10.test.images, y_: cifar10.test.labels})
            print("step %d, training accuracy %g" % (i, train_accuracy))
        train_step.run(feed_dict={x: batch[0], y_: batch[1]})

    print("test accuracy %g" % accuracy.eval(feed_dict={
        x: cifar10.test.images, y_: cifar10.test.labels}))


if __name__ == '__main__':
    tf.app.run(main=main)
