#! /usr/bin/python
#*
#* Author : Suneesh Babu (suneesh@juniper.net)
#* Program : CPU_Memory_Usage.py
#* Platform : Python Any platform with matplotlib libraries
#* Version : 1.2
#* Description :
#* CPU_Memory_Usage.py is a charting tool, which helps to draw cpu and memory usages of 
#* different processes running on JUNOS(or any system). The Tool is configurable on 
#* the number of processes to monitor, number of iterations for monitoring, 
#* and interval at which data is polled
#*
#* Copyright (c) 2014 Juniper Networks. All Rights Reserved.
#*
#* YOU MUST ACCEPT THE TERMS OF THIS DISCLAIMER TO USE THIS SOFTWARE,
#* IN ADDITION TO ANY OTHER LICENSES AND TERMS REQUIRED BY JUNIPER NETWORKS.
#*
#* JUNIPER IS WILLING TO MAKE THE INCLUDED SCRIPTING SOFTWARE AVAILABLE TO YOU
#* ONLY UPON THE CONDITION THAT YOU ACCEPT ALL OF THE TERMS CONTAINED IN THIS
#* DISCLAIMER. PLEASE READ THE TERMS AND CONDITIONS OF THIS DISCLAIMER
#* CAREFULLY.
#*
#* THE SOFTWARE CONTAINED IN THIS FILE IS PROVIDED "AS IS." JUNIPER MAKES NO
#* WARRANTIES OF ANY KIND WHATSOEVER WITH RESPECT TO SOFTWARE. ALL EXPRESS OR
#* IMPLIED CONDITIONS, REPRESENTATIONS AND WARRANTIES, INCLUDING ANY WARRANTY
#* OF NON-INFRINGEMENT OR WARRANTY OF MERCHANTABILITY OR FITNESS FOR A
#* PARTICULAR PURPOSE, ARE HEREBY DISCLAIMED AND EXCLUDED TO THE EXTENT
#* ALLOWED BY APPLICABLE LAW.
#*
#* IN NO EVENT WILL JUNIPER BE LIABLE FOR ANY DIRECT OR INDIRECT DAMAGES,
#* INCLUDING BUT NOT LIMITED TO LOST REVENUE, PROFIT OR DATA, OR
#* FOR DIRECT, SPECIAL, INDIRECT, CONSEQUENTIAL, INCIDENTAL OR PUNITIVE DAMAGES
#* HOWEVER CAUSED AND REGARDLESS OF THE THEORY OF LIABILITY ARISING OUT OF THE
#* USE OF OR INABILITY TO USE THE SOFTWARE, EVEN IF JUNIPER HAS BEEN ADVISED OF
#* THE POSSIBILITY OF SUCH DAMAGES.
#*


import sys
import re
import matplotlib.pyplot as mplot
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from itertools import islice
import matplotlib as mpl
import logging
from sys import argv
from datetime import datetime
import pexpect
import os
import argparse
import time

timestamp = []
cpu_usage = []
mem_usage = []
mem_value = []
#process_list = ['rpd','ppmd','mib2d','chassisd']
process_list = []
colours = []

currenttime = datetime.now().strftime("_%d_%m_%Y_%H_%M")
cpu_memory_result = 'CPU_Memory_Usage' + currenttime + '.pdf' 
#top_raw_data =  'top_raw_data' + currenttime + '.txt'
top_raw_data =  'top_raw_data' + currenttime
#pp = PdfPages(cpu_memory_result)


def main():
  mpl.rcParams['font.size'] = 9.0
  script = os.path.basename(__file__)

  parser = argparse.ArgumentParser()
  if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)
  parser.add_argument('--ip', type = str, help = "IP Address of the Router")
  parser.add_argument('--top', type = str, help = "No-of-Processes,Iterations,Measure-Interval(sec)")
  parser.add_argument('--process', type = str, help = "Process List")

  args = parser.parse_args()
  host_ip = args.ip.strip('')
  top_value = args.top.split(',')
  num_processes = int(top_value[0])
  no_iteration = int(top_value[1])
  measure_interval = int(top_value[2])
  process_list = args.process.split(',')

  tot_time = int(no_iteration) * int(measure_interval)
  
  logfile = script.strip(".py")
  getLogs(logfile,currenttime)

  logging.info('Total Execution time is: ' + str(tot_time))
  no_top_exec = int (tot_time / 3600)
  logging.info('No of Top Fresh Triggers: ' + str(no_top_exec))
  if (tot_time > 3600):
    no_iteration = int(3600 / int(measure_interval))
    top_files = []
    for i in range (1, (no_top_exec+1)):
      data_file = top_raw_data + '_' + str(i) + '.txt'
      top_files.append(data_file)
      top_and_getData(host_ip,data_file, num_processes, no_iteration, measure_interval )
  
    with open('top_collated.txt', 'w') as outfile:
      for fname in top_files:
        with open(fname) as infile:
          for line in infile:
            outfile.write(line)
    file = "top_collated.txt"
  else:
    top_and_getData(host_ip,top_raw_data, num_processes, no_iteration, measure_interval )
    file = top_raw_data
  #top_and_getData(host_ip,top_raw_data, num_processes, no_iteration, measure_interval )
  
  #file = top_raw_data
  #file = "top_collated.txt"
  fd_file = open (file)

  pp = PdfPages(cpu_memory_result)
  
  colours = colourInitilize()
  for process in process_list:
    getCPUUsage(fd_file,process)
    colour = colourSelector(colours)
    getLineOutput(colour,cpu_usage,'Time(sec*iteration)','CPU Usage(%)','CPU Usage of RE Processes',process)
    clearArray()
  saveOutput(pp) #png and pdf works
  mplot.clf()

  colours = colourInitilize()
  for process in process_list:
    mem_value = getMemUsage(fd_file,process)
    colour = colourSelector(colours)
    logging.info('Memory info form Main ::: ')
    logging.info(mem_value)
    getLineOutput(colour,mem_value,'Time(sec*iteration)','MEMORY Usage(M)', 'MEMORY Usage of RE Processes', process)
    clearArray()
  saveOutput(pp) #png and pdf works
  mplot.clf()

  '''
     The tool Draws Stacked Bar Chart, Bar Chart & Pie Chart only for shorter duration
  '''
  if ((no_iteration < 51) or (tot_time < 610)):
    logging.info('---------------- Shorter Duration Run ----------------')
    logging.info('Drawing the Stacked Bar Chart for Processes CPU Usage')
    logging.info('------------------------------------------------------')
    getSBChart(fd_file, num_processes, no_iteration, process_list)
    saveOutput(pp) #png and pdf works
    mplot.clf()
  
    #Draw the Pie Chart for each interval of top polling
    logging.info('Drawing the PieChart for Processes CPU Usage')
    logging.info('--------------------------------------------')
    getTimeStamp(fd_file)
    getLabels_Sizes(fd_file,'PieChart',num_processes, no_iteration,pp)
    logging.info('Drawing the BarChart for Processes CPU Usage')
    logging.info('--------------------------------------------')
    getTimeStamp(fd_file)
    getLabels_Sizes(fd_file,'BarChart',num_processes, no_iteration,pp)
  
  fd_file.close()
  pp.close()


def getSBChart(fd_file, num_processes, no_iteration, process_list):
  '''
     (file_descriptor,int,int,list) --> Stacked Bar Chart
     Returns the Stacked Bar Chart
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  labels = []
  sizes = []
  start = 8
  stop = start + int(num_processes)
  process_select = []
  cpu_list = []
  dict_1 = {}
  dataset = []
  data_orders = []
  getTimeStamp(fd_file)
  for i in range(1,int(no_iteration) + 1):
    for process in process_list:
      process_select.append(process)
    head = list(islice(fd_file,start,stop))
    for line in head:
      process_name = re.search("\%\s[0-9a-zA-B-]+$",line)
      cpu_value = re.search("\w{1,3}\.\w\w\%\s",line)
      for process in process_select:
        if (process == process_name.group().strip("% ")):
          labels.append(process_name.group().strip("% "))
          sizes.append(float(cpu_value.group().strip("% ")))
          process_select.remove(process)
    while (len(process_select) > 0):
      logging.debug('Process Select ==>')
      logging.debug(process_select)
      for process in process_select:
        labels.append(process)
        sizes.append(0.00)
        process_select.remove(process)
        logging.debug('After Removing the process Select ==>')
        logging.debug(process_select)
    
    logging.debug('Labels are ==>')
    logging.debug(labels)
    logging.debug('CPU Usage is ==>')
    logging.debug(sizes)
    temp_list = []        
    for item in labels:
      temp_list.append(item)
    data_orders.append(temp_list)
    
    dict_1 = dict(zip(labels,sizes))
    #print "Dictionary is ", dict_1
    logging.debug('Dictionary is ==> ')
    logging.debug(dict_1)
    dict_2 = dict_1
    dataset.append(dict_2)
    dict_1 = {}
    
    del labels[:]
    del sizes[:]
  
  logging.debug('Final Data Set is ==>')
  logging.debug(dataset)
  logging.debug('Final Data Order is ==>')
  logging.debug(data_orders)
  
  colors = colourInitilize()
  names = sorted(dataset[0].keys())
  values = np.array([[data[name] for name in order] for data,order in zip(dataset, data_orders)])
  lefts = np.insert(np.cumsum(values, axis=1),0,0, axis=1)[:, :-1]
  orders = np.array(data_orders)
  bottoms = np.arange(len(data_orders))
  logging.debug('Values ==>')
  logging.debug(values)
  logging.debug('Lefts ==>')
  logging.debug(lefts)
  logging.debug('Orders ==>')
  logging.debug(orders)
  logging.debug('Bottoms ==>')
  logging.debug(bottoms)
  
  for name, color in zip(names, colors):
    idx = np.where(orders == name)
    value = values[idx]
    left = lefts[idx]
    mplot.bar(left=left, height=0.8, width=value, bottom=bottoms, 
            color=color, orientation="horizontal", label=name)
  mplot.yticks(bottoms+0.4, [timestamp[t] % (t+1) for t in bottoms])
  mplot.legend(loc="best", bbox_to_anchor=(1.0, 1.00))
  mplot.title('CPU Usage of RE Processes')
  mplot.xlabel('CPU Usage(%)')
  mplot.subplots_adjust(right=0.85)
  
  fd_file.seek(0)  


def getTimeStamp(fd_file):
  '''
     (file_descriptor) --> list
     Returns a list of timestamps at which top data is polled
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  for line in fd_file:
    time = re.search("\d\d\:\d\d\:\d\d$",line)
    if(time):
      timestamp.append(time.group())
  logging.info('Time Stamp is ::: ')
  logging.info(timestamp)
  fd_file.seek(0)

def getCPUUsage(fd_file, process_name):
  '''
     (file_descriptor, str) --> list
     Returns a list with CPU usage of the given process
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  for line in fd_file:
    process = re.search(process_name,line)
    if(process):
      logging.debug('Process ===> ' + process.group())
      cpu = re.search("\d?\d?\d\.\d\d\%\s",line)
      if(cpu):
        cpu_usage.append(float(cpu.group().strip("% ")))
  fd_file.seek(0)
  logging.info('CPU Usage ::: ')
  logging.info(cpu_usage)
  return  cpu_usage 

def getMemUsage(fd_file, process_name):
  '''
     (file_descriptor, str) --> list
     Returns a list with Memory usage of the given process
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  for line in fd_file:
    process = re.search(process_name,line)
    if(process):
      logging.debug('Process ===> ' + process.group())
      line_items = line.split()
      mem_usage.append(line_items[5].strip(" "))
  fd_file.seek(0)
  logging.info('Memory Before Converting ::: ')
  logging.info(mem_usage)
  mem_value = memoryConverter(mem_usage)
  logging.info('Memory After Converting ::: ')
  logging.info(mem_value)
  return mem_value  

def getLineOutput(colour,y_value,xlabel,ylabel,title,process):
  '''
     (str,list,str,str,str,str) --> line graph
     Returns a line graph of the given process
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  x = np.arange(len(y_value))
  y = y_value
  mplot.xlabel(xlabel)
  mplot.ylabel(ylabel)
  mplot.title(title)
  logging.info('x-axis ::: ')
  logging.info(x)
  logging.info('y-axis ::: ')
  logging.info(y)
  mplot.plot(x,y,color=colour,label=process)
  mplot.legend(loc='lower right')

    
def saveOutput(pp):
  '''
     Returns the Graph in PDF format
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  mplot.savefig(pp, format='pdf')

def clearArray():
  '''
     Returns the list with empty elements
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  del cpu_usage[:]
  del mem_usage[:]
  del mem_value[:]

def colourSelector(colours):
  '''
     (list) --> str
     Returns the first color of the list of colors
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  colour = colours[0]
  del colours[0]
  return colour

def colourInitilize():
  '''
     Returns the list of colors
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  colours = ['red','green','blue','cyan','magenta','yellow','black',
                'yellowgreen', 'gold', 'lightskyblue', 'lightcoral']
  return  colours   

def memoryConverter(mem_list):
  '''
     (list) --> list
     Returns a list of memory values in M 
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  mem_output = []
  for item in mem_list:
    matchObjK = re.match('\w+K',item)
    if (matchObjK):
      item = item.strip('K')
      value = float(int(item) / 1024)
      mem_output.append(int(value))
    matchObjM = re.match('\w+M',item)
    if (matchObjM):
      value = item.strip('M')
      mem_output.append(float(value))
  return mem_output


def getLabels_Sizes(fd_file,chartType,num_processes, no_iteration,pp):
  '''
     (file_descriptor, str, int, int) --> list
     Returns the labels used to draw PIE chart or BAR chart
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  labels = []
  sizes = []
  start = 8
  stop = start + int(num_processes)
  process_list = []
  cpu_list = []
  for i in range(1,int(no_iteration)+1):
    head = list(islice(fd_file,start,stop))
    for line in head:
      cpu_value = re.search("\w{1,3}\.\w\w\%\s",line)
      if(cpu_value):
        logging.info('CPU Usage ::: ' + cpu_value.group().strip("%"))
        zero_check = re.match("^0\.00?$",cpu_value.group().strip("% "))
        if(zero_check):
          logging.info(cpu_value.group().strip("%") + ' is taking ZERO CPU')
          #print "Process is taking ZERO CPU"
        else:
          sizes.append(float(cpu_value.group().strip("% ")))
          process_name = re.search("\%\s[0-9a-zA-B-]+$",line)
          if(process_name):
            logging.info('Process Name ::: ' + process_name.group().strip("% "))
            labels.append(process_name.group().strip("% "))
    sum = 0.0
    idle = 0.0
    for item in sizes:
      sum = sum + item
    if (sum == 100.0):
      idle = 0.0
    else:
      idle = 100.00 - sum
    sizes.append(idle)
    labels.append('idle') 
  
    if(chartType == 'PieChart'):
      logging.info('-----------Plotting Pie Chart-----------')
      getPieChart(labels,sizes,pp)
    if(chartType == 'BarChart'):
      logging.info('-----------Plotting Bar Chart-----------')
      getBarChart(labels,sizes,pp)
    del labels[:]
    del sizes[:]
  fd_file.seek(0)  


def getPieChart(labels,sizes,pp):
  '''
     (list,float) --> Pie Chart
     Returns the Pie Chart from the labels
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  colors = colourInitilize()
  #explode = (0, 0.1, 0, 0, 0, 0, 0, 0, 0, 0) # only "explode" the 2nd slice
  explode = None

  mplot.pie(sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.2f%%', shadow=True)

  mplot.axis('equal')
  mplot.title('CPU Usage @ '+ timestamp[0], bbox={'facecolor':'0.8', 'pad':5}, ha='left')
  del timestamp[0]
  mplot.savefig(pp, format='pdf')
  mplot.clf()   


def getBarChart(labels,sizes,pp):
  '''
     (list,float) --> Bar Chart
     Returns the Bar Chart from the labels
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  height = []
  for item in sizes:
    height.append(int(item))
  colors = colourInitilize()
  ind = np.arange(len(height))
  width = 0.35
  mplot.bar(ind, height, width, color=colors,align='center')
  mplot.xlabel('Process')
  mplot.ylabel('CPU Usage(%)')
  mplot.xticks(ind,labels)
  mplot.title('CPU Usage @ '+ timestamp[0], bbox={'facecolor':'0.8', 'pad':5}, ha='left')
  del timestamp[0]
  mplot.savefig(pp, format='pdf')
  mplot.clf()   


def getLogs(logfile,currenttime):
  '''
     (str,str) --> str
     Returns handle for logging
  '''
  logging.basicConfig(filename=logfile + currenttime + '.log',level=logging.DEBUG, 
                      format='%(asctime)s %(message)s')
  

def top_and_getData(host_ip,file, num_processes, no_iteration, measure_interval):
  '''
     (str,str,int,int,int) --> file
     Returns the top raw-data for Charting
  '''
  logging.info('\nFunction Name :: ' + sys._getframe().f_code.co_name + '\n')
  username = 'regress'
  time_of_exec = int((int(no_iteration) * int(measure_interval) ) + 10)
  ssh_command = 'ssh ' + username + '@' + host_ip
  logging.info('SSH Command :: ' + ssh_command)

  top_command = 'top -d ' + str(no_iteration) + ' -s ' + str(measure_interval) \
                  + ' -i ' + str(num_processes) + ' >> /var/tmp/' + str(file)
  
  logging.info('TOP Command :: ' + top_command)
  #ftp_command = 'ftp ' + username + '@' + host_ip
  ftp_command = 'ftp ' + host_ip
  logging.info('FTP Command :: ' + ftp_command)
  transfer_command = 'get ' + file
  logging.info('File Transfer Command :: ' + transfer_command)
  
  router = pexpect.spawn(ssh_command,timeout=time_of_exec)
  out = router.expect(['[P|p]assword','(yes/no)?'], timeout=time_of_exec)
  if out == 0:
    router.sendline('MaRtInI')
  if out == 1:
    router.sendline('yes')
    router.expect('[P|p]assword:')
    router.sendline('MaRtInI')
  router.expect("% ")
  router.sendline('su')
  router.expect("Password:")
  router.sendline('Embe1mpls')
  router.expect("%")
  router.sendline('cd /var/tmp')
  router.expect("% ")
  router.sendline('rm -rf top_raw_data_*')
  router.expect("% ")
  router.sendline(top_command)
  for i in range(1,time_of_exec):
    time.sleep(1)
  router.close()

  router = pexpect.spawn(ftp_command,timeout=time_of_exec)
  router.expect(":")
  router.sendline('regress')
  router.expect("assword:")
  router.sendline('MaRtInI')
  router.expect("> ")
  router.sendline('cd /var/tmp')
  router.expect("> ")
  router.sendline('bin')
  router.expect("> ")
  router.sendline(transfer_command)
  router.expect("> ")
  router.sendline('bye')
  router.close()


if __name__ == '__main__':
  main()

