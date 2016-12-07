#!/usr/bin/env python

import rospy
import sys
import math
import time
import itertools

import numpy                 as np
import matplotlib.pyplot     as plt
import matplotlib            as mpl

from scipy                   import linalg
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
# Sphero speed 
SPD = 60 
# Position error threshold 
THR = 0.1

pub = rospy.Publisher('cmd_vel', Twist, queue_size=10)

index = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32]
group_counter = dict((el,0) for el in index)
group_theta = dict((el,0) for el in index)
group_ts = dict((el,0) for el in index)
group_theta_ts_max = dict((el,0) for el in index)
group_ts_max = dict((el,-9999) for el in index)
kmeans = KMeans(random_state=0)
gmm_model = mixture.GaussianMixture(covariance_type='full')
last_group = 0
last_state = 0
previous_state = dict((el,0) for el in index)
f = open('./data/data_process-' + str(time.time()) + '.txt', 'w+')

curTheta = 0
curTwist = Twist()  

autoPositioning = True

pos = []
timestamps = [] 
dirc = []

last_x = -999999
last_y = -999999

color_iter = itertools.cycle(['navy', 'c', 'cornflowerblue', 'gold',
                              'darkorange'])

def plot_results(X, Y, means, covariances, index, title):
    splot = plt.subplot(1, 1, 1 + index)
    for i, (mean, covar, color) in enumerate(zip(
            means, covariances, color_iter)):
        v, w = linalg.eigh(covar)
        v = 2. * np.sqrt(2.) * np.sqrt(v)
        u = w[0] / linalg.norm(w[0])
        # as the DP will not use every component it has access to
        # unless it needs it, we shouldn't plot the redundant
        # components.
        if not np.any(Y == i):
            continue
        plt.scatter(X[Y == i, 0], X[Y == i, 1], .8, color=color)

        # Plot an ellipse to show the Gaussian component
        angle = np.arctan(u[1] / u[0])
        angle = 180. * angle / np.pi  # convert to degrees
        ell = mpl.patches.Ellipse(mean, v[0], v[1], 180. + angle, color=color)
        ell.set_clip_box(splot.bbox)
        ell.set_alpha(0.5)
        splot.add_artist(ell)

    plt.xlim(0., 10.)
    plt.ylim(0., 16.)
    plt.title(title)
    plt.xticks(())
    plt.yticks(())

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def createTwist(lx, ly): 
    newTwist = Twist()
    newTwist.linear.x = lx
    newTwist.linear.y = ly
    newTwist.linear.z = 0
    newTwist.angular.x = 0
    newTwist.angular.y = 0
    newTwist.angular.z = 0
    return newTwist

def CalcHeading (src, dst) : 
  height = dst[1] - src[1] 
  base   = dst[0] - src[0] 

  return math.atan2(height, base) 

def IsCloseEnough (src, dst) : 
  global THR
  height = dst[1] - src[1] 
  base   = dst[0] - src[0] 
  dist   = math.sqrt(math.pow(height, 2) + math.pow(base, 2))

  return (dist < THR) 

# ----------------------------------------------------------------------
# Callback functions
# ----------------------------------------------------------------------

def init_model():
    global index
    global group_counter
    global group_theta
    global kmeans
    global gmm_model
    global pos 
    global timestamps 
    global dirc 
    global last_x
    global last_y

    # result storage
    index = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32]
    group_counter = dict((el,0) for el in index)
    group_theta = dict((el,0) for el in index)

    # data preprocess
    my_data = genfromtxt('./data/frames.txt', delimiter=',')

    dataSet = np.array(my_data)
    pos, timestamps, dirc = np.split(my_data, [2, 3], axis = 1)

    m, n = pos.shape
    last = pos[m - 1,[0,1]] 
    last_x = last.item(0)
    last_y = last.item(1)
    # get the average timestamp for each cluster
    f.write("last position info: \n") 
    f.write("postion in file: " + str(last) + "\n") 
    f.write("last_x: " + str(last_x) + "last_y: " + str(last_y) + "\n") 

    # TODO: cross-validation
    # issue: unsupervised learning -> how to get label
    # basic trade-off between # of clusters:
    # more clusters: accrate but some critical states may be missed and lost the entire trace
    # less clusters: easy to move forward, but in less accurate way
    # k: number of clusters
    k = 16
    # get init means for Gaussian Mixture Model
    kmeans.set_params(n_clusters = k)
    kmeans.fit(pos)

    # fit a Gaussian Mixture Model
    # gmm_model.set_params(n_components = k, means_init=kmeans.cluster_centers_)
    # Defaul init_params: kmeans
    gmm_model.set_params(n_components = k)
    gmm_model.fit(pos)

    # cluster the origin data to get group orientation
    clustring_result = gmm_model.predict(pos)

    # plot result
    plot_results(pos, clustring_result, gmm_model.means_, gmm_model.covariances_, 0, 'Expectation-maximization')
    plt.show()

    # get timestamp and direction for each cluster
    index_counter = 0

    # sum up all the timestamps/directions inside one cluster
    for x in np.nditer(clustring_result):
        group_number = x.item(0)
        group_counter[group_number] = group_counter[group_number] + 1
        group_theta[group_number] = group_theta[group_number] + dirc.item(index_counter)
        group_ts[group_number] = group_ts[group_number] + timestamps.item(index_counter)
        if group_ts_max[group_number] < timestamps.item(index_counter):
            group_theta_ts_max[group_number] = dirc.item(index_counter)
            group_ts_max[group_number] = timestamps.item(index_counter)
        index_counter = index_counter + 1

    # get the average timestamp for each cluster
    f.write("clustering info: \n") 
    f.write("cluster timestamp: \n") 
    for key, value in group_ts.iteritems():
        f.write("cluster number: " + str(key) + "\n")
        f.write("# of elements in cluster: " + str(group_counter[key]) + "\n")
        if group_counter[key] == 0:
            value = value
        else:
            value = value / group_counter[key]
            if abs(group_theta_ts_max[key] - value) > 0.3:
                value = group_theta_ts_max[key]
        group_ts[key] = value
        f.write("cluster timestamp: " + str(value) + "\n")

    # get the average direction for each cluster
    f.write("\n\n") 
    f.write("cluster theta: \n") 
    for key, value in group_theta.iteritems():
        f.write("cluster number: " + str(key) + "\n")
        f.write("# of elements in cluster: " + str(group_counter[key]) + "\n")
        if group_counter[key] == 0:
            value = value
        else:
            value = value / group_counter[key]
        group_theta[key] = value
        f.write("cluster theta: " + str(value) + "\n")
    f.write("\n")
    f.write("\n")

def myCallback(data):
    global SPD
    global group_theta
    global group_ts
    global gmm_model
    global last_state
    global last_group
    global pub
    global curTheta
    global curTwist
    global autoPositioning
    global last_x
    global last_y

    # For Sphero 
    PosX = data.pose.pose.position.x
    PosY = data.pose.pose.position.y
    PosT = math.atan2(data.twist.twist.linear.y, data.twist.twist.linear.x)

    # Initial positioning 
    if autoPositioning : 
      print ( "Initial positioning ... \n" ) 
      if ( not IsCloseEnough([PosX, PosY], [pos[0][0], pos[0][1]]) ) : 
        print ( "Current position: " + str(PosX) + ", " + str(PosY) + "\n" ) 
        print ( "Heading position: " + str(pos[0][0]) + ", " + str(pos[0][1]) + "\n" ) 
        curTheta = CalcHeading( [PosX, PosY], [pos[0][0], pos[0][1]] ) 
        curTwist = createTwist( SPD * math.cos(curTheta), SPD * math.sin(curTheta) )  
        pub.publish( curTwist )
        return 
      else : 
        print ( "Initial positioning complete \n") 
        pub.publish(createTwist(0, 0)) 
        rospy.sleep(1) 
        autoPositioning = False 
        return 

    pos_group = gmm_model.predict([PosX, PosY]).reshape(1, -1).item(0)
    print(pos_group) 
    new_ts = group_ts[pos_group]
    last_ts = group_ts[last_group]

    if last_group == 0:
        last_ts = 0
    # choose group with timestamp checking
    if new_ts < last_ts:
        pos_group = last_group
    else:
        last_group = pos_group

    # get new target theta
    new_theta = group_theta[pos_group]

    curTheta = new_theta
    curTwist = createTwist(SPD * math.cos(curTheta), SPD * math.sin(curTheta))  

    distance = (PosX - last_x) * (PosX - last_x) + (PosY - last_y) * (PosY - last_y)
    if distance < 0.1:
        newTwist = createTwist(0.0, 0.0)

    # curTwist = createTwist(0, 0) 

    # in-state checking
    # if last_state == pos_group:
    #     curTwist = createTwist(SPD * math.cos(PosT), SPD * math.sin(PosT))  
    # else:
    #     if abs(new_theta - PosT) < 0.1:
    #         last_state = pos_group

    print ("Publish new twist")    
    pub.publish(curTwist)

    # print (rospy.get_caller_id() + ' heard currentPos' + "\n")
    # print (data)
    # print ("\n\n")
    # print ("In group: " + str(pos_group) + ' and make head turn to: ' + str(new_theta) + "\n")
    # print ("\n\n")

    f.write(rospy.get_caller_id() + ' heard currentPos' + "\n")
    f.write('x: ' + str(PosX) + ',' + 'y: ' + str(PosY) + ',' + 'theta: ' +  str(PosT) +"\n" )
    f.write('Destination position: (' + str(last_x) + ', ' + str(last_y) +")\n" )
    f.write('Distance to Destination: ' + str(distance) +"\n" )
    f.write("In group: " + str(pos_group) + ' and make head turn to: ' + str(new_theta) + "\n")
    f.write("\n")
    f.write("\n")

def DataProcess():
    init_model()
    rospy.init_node('data_process', anonymous=True)

    # For Sphero 
    rospy.Subscriber('odom', Odometry, myCallback)

    rospy.spin()

if __name__ == '__main__':
    DataProcess()

