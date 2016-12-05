#!/usr/bin/env python

import rospy
import sys
import math
import numpy                 as np

from numpy                   import genfromtxt
from sklearn.cluster         import KMeans
from sklearn                 import mixture
from geometry_msgs.msg       import Twist
from turtlesim.msg           import Pose
from std_msgs.msg            import String
from nav_msgs.msg            import Odometry

# ----------------------------------------------------------------------
# Configuration Constants 
# ----------------------------------------------------------------------
# TODO
# Sphero speed 
SPD = 50 

# TODO
# For simulation ---------------------------------------------------
# pub = rospy.Publisher('/turtle1/cmd_vel', Twist, queue_size=10)
# For Sphero -------------------------------------------------------
pub = rospy.Publisher('cmd_vel', Twist, queue_size=10)

index = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32]
group_counter = dict((el,0) for el in index)
group_theta = dict((el,0) for el in index)
kmeans = KMeans(n_clusters=16, random_state=0)
gmm_model = mixture.GaussianMixture(n_components=16, covariance_type='full')
last_state = 0
previous_state = dict((el,0) for el in index)

def init_model():
    global index
    global group_counter
    global group_theta
    global kmeans
    global gmm_model

    # result storage
    index = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32]
    group_counter = dict((el,0) for el in index)
    group_theta = dict((el,0) for el in index)

    # data preprocess
    my_data = genfromtxt('frames.txt', delimiter=',')
    dataSet = np.array(my_data)
    pos, dirc, dummy = np.split(my_data, [2, 3], axis = 1)

    # get init means for Gaussian Mixture Model
    kmeans.fit(pos)
    # fit a Gaussian Mixture Model
    #clf = mixture.GaussianMixture(n_components=16, covariance_type='full', means_init =             kmeans.cluster_centers_)
    gmm_model.set_params(means_init=kmeans.cluster_centers_)
    gmm_model.fit(pos)

    # cluster the origin data to get group orientation
    clustring_result = gmm_model.predict(pos)

    index_counter = 0
    for x in np.nditer(clustring_result):
        group_number = x.item(0)
        group_counter[group_number] = group_counter[group_number] + 1
        group_theta[group_number] = group_theta[group_number] + dirc.item(index_counter)
        index_counter = index_counter + 1
    for key, value in group_theta.iteritems():
        if group_counter[key] == 0:
            value = value
        else:
            value = value / group_counter[key]
        group_theta[key] = value


def myCallback(data):
    global SPD
    global group_theta
    global gmm_model
    global last_state
    global pub

    # TODO
    # For simulation
    # PosX = data.x
    # PosY = data.y
    # PosT = data.theta
    # For Sphero 
    PosX = data.pose.pose.position.x
    PosY = data.pose.pose.position.y
    PosT = math.atan2(data.twist.twist.linear.y, data.twist.twist.linear.x)

    pos_group = gmm_model.predict([PosX, PosY]).reshape(1, -1).item(0)
    new_theta = group_theta[pos_group]

    newTwist = createTwist(SPD * math.cos(new_theta), SPD * math.sin(new_theta))  
    pub.publish(newTwist)
    print ("Publish new twist")

    # if not last_state == pos_group : 
    #   newTwist = createTwist(SPD * math.cos(new_theta), SPD * math.sin(new_theta))  
    #   pub.publish(newTwist)
    #   print ("Publish new twist")

    #   if abs(new_theta - PosT) < 0.1:
    #       last_state = pos_group

    print (rospy.get_caller_id() + ' heard currentPos' + "\n")
    print (data)
    print ("\n\n")
    print ("In group: " + str(pos_group) + ' and make head turn to: ' + str(new_theta) + "\n")
    print ("\n\n")

# -- Chunheng Luo 
# Changed function signiture 
# Original code 
#def createTwist(lx, az):
# Changed 
def createTwist(lx, ly): 
    newTwist = Twist()
    newTwist.linear.x = lx
    newTwist.linear.y = ly
    newTwist.linear.z = 0
    newTwist.angular.x = 0
    newTwist.angular.y = 0
    # Original code 
    #newTwist.angular.z = az
    # Changed 
    newTwist.angular.z = 0
    return newTwist

def DataProcess():
    init_model()
    rospy.init_node('data_process', anonymous=True)

    # TODO
    # For simulation
    # rospy.Subscriber('turtle1/pose', Pose, myCallback)
    # For Sphero 
    rospy.Subscriber('odom', Odometry, myCallback)

    rate = rospy.Rate(10)
    while not rospy.is_shutdown():
        rate.sleep()

if __name__ == '__main__':
    DataProcess()

