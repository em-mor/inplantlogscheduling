from mesa import Agent
from collections import deque
import numpy as np
import random
import sys
import pandas as pd

class AMR(Agent):
    #amr agent class
    
    def __init__(self,unique_id,model,warehouse_inf,closed_loop_route,
                 check_time):
        
        super().__init__(unique_id,model)
        self.warehouse_inf = warehouse_inf
        self.batterylife = random.randint(10000,36000)  #max 10h = 36000 time steps
        self.velocity = 1
        self.charging_speed = 5
        self.location = np.array([1,1])
        self.assigned_tasks = deque()
        self.state = [0,1]       #1st idx for [0,1,2] for idle, busy or charging, 2nd idx for counter
        self.chosen_charging_idx = -1
        self.task = None
        self.task_state = -1
        self.task_station = 0  
        self.loop_state = 0
        self.route = closed_loop_route
        self.created = False
        self.loading_time = 60
        self.loaded = 0    
        self.check_dropoff = True
        self.check_time = check_time
        self.two_task_time = 780    
        
        self.tasks_created = 0
        self.tasks_created_1 = 0
    
    def check_battery(self):
        
        queue = []
        for i in self.model.charging_stations:
            if len(i.queue) == 0:
                queue.append(i)
        # check if battery can be charged
        if (len(self.assigned_tasks) == 0 and self.task == None and self.state[0] == 0 and 
        ((self.batterylife < 18000 and self.state[1] > 15 and len(queue) > 0) 
         or self.batterylife < 9000)):
            #change the state to charging
            self.state = [2,0]
            #selects the charging station with the shortest queue
            self.chosen_charging_idx = np.argmin([len(chargingstation.queue) for chargingstation in self.model.charging_stations])
        #if a charging station has been selected it drives to the charging station
        if self.chosen_charging_idx != -1:
            #count the amount of time spend in the charging state
            self.state[1] += 1
            #check the location of the charging station
            move_location = self.model.charging_stations[self.chosen_charging_idx].location
            if sum(move_location != self.location) != 2:
                #if transported change the location
                self.location = move_location
            #append the amr to the queue at the charging station
            if self not in self.model.charging_stations[self.chosen_charging_idx].queue:
                self.model.charging_stations[self.chosen_charging_idx].queue.append(self)

    def move(self,destiny_location):
        
        #function that moves the amr in straight lines to the wanted location
        #first in the x direction than in the y direction 
        difference = self.location - destiny_location
        if difference[0] != 0 or difference[1] != 0:
            if difference[0] < 0:
                self.location[0] += self.velocity
            elif difference[0] > 0:
                self.location[0] -= self.velocity
            elif difference[1] < 0:
                self.location[1] += self.velocity
            elif difference[1] > 0:
                self.location[1] -= self.velocity
                
    def update_state(self):

        #when there are no assigned tasks and there is no current task then the state is idle
        if len(self.assigned_tasks) == 0 and self.state[0] != 2 and self.state[0] != 3 and self.state[0] != 4:
            if self.state[0] == 0:
                self.state[1] += 1
            else: 
                self.state[0] = 0
                self.state[1] = 1
        elif len(self.assigned_tasks) != 0 and self.state[0] != 2 and self.state[0] != 3 and self.state[0] != 4:
            if self.state[0] == 1:
                self.state[1] += 1
            else: 
                self.state[0] = 1
                self.state[1] = 1
        elif self.state[0] == 4:
            self.state[1] += 1
    
    def check_buffer_content(self,i):
        
        #function that checks the buffer content, and if the buffer is full
        #a task is created to pickup a pallet
        for key,value in self.model.stations[i].buffer.iterrows():
            #if there are products present in the buffer
            if value[0] > 0:
                product = self.model.stations[i].production_list.loc[(self.model.stations[i].production_list['Id_product']==key)]
                ulcycle = product['# UL/cycle'].values[0]
                material = -1
                release = self.model.current_timestep
                goal = self.model.current_timestep + 700
                #check if producing now or already finished
                if not self.model.stations[i].produce_product.empty:
                    #check if the products in the buffer are the same as the ones
                    #which are being produced now
                    if key != self.model.stations[i].produce_product['Id_product']:
                        #if product batch is finished get the maximum amount possible
                        amount = min(ulcycle,value[0])
                    #if it is the same product batch check if there is one cycle present
                    #in the buffer to pickup
                    elif (key == self.model.stations[i].produce_product['Id_product'] 
                          and value[0] >= self.model.stations[i].produce_product['# UL/cycle']):
                        amount = self.model.stations[i].produce_product['# UL/cycle']
                    else:
                        return None
                #check if production is finished 
                elif self.model.stations[i].production_index > len(self.model.stations[i].production_list):
                    amount = ulcycle
                else:
                    return None
                #create new task
                cycle = self.model.stations[i].produce_product['# UL/cycle']
                product = key
                new_task = self.create_task(self.model.stations[i].unique_id,material
                                            ,release,goal,amount,cycle,product)
                self.model.stations[i].outstanding_tasks.append(new_task)
                self.assigned_tasks.insert(1,new_task)
                self.created = True
                return new_task
    
    def dropoff(self):
        
        #function to do a dropoff of raw materials
        self.counter += 1
        #if amr not in the queue at the station append it and change state to waiting
        if self.unique_id not in self.task_station.amr_queue and self.task_state == 3:
            self.task_station.amr_queue.append(self.unique_id)
            self.state = [4,1]
        #if the amr in the queue at the station and in front change the state of the task
        elif self.unique_id in self.task_station.amr_queue and self.task_state == 3:
            if (self.task_station.amr_queue.index(self.unique_id) == 0 or 
            self.task_station.amr_queue.index(self.unique_id) == 1):
                self.counter = 0
                self.task_state = 4
        #if the amr at the queue and emptied for loading_time timesteps append the raw materials to the queue
        elif self.counter >= self.loading_time and self.task_state == 4:
            self.loaded = 0
            if self.task not in self.task_station.outstanding_tasks:
                print(self.task)
                print(self.task_station.outstanding_tasks)
            #delete the amr from the queue and change the state to busy
            del self.task_station.amr_queue[self.task_station.amr_queue.index(self.unique_id)]
            self.state = [1,1]
            #from production station point of view task is finished, so remove from tasks
            #and change the state of the task
            self.task_station.outstanding_tasks.remove(self.task)
            #check if there is still material left in the queue
            if not self.task_station.produce_product.empty:
                material = self.task_station.raw_mat_inf.loc[(self.task_station.raw_mat_inf['Componente']==self.task[1])]
                if self.task_station.inventory.loc[self.task[1]].values[0] > material['use per time'].values[0]:
                    self.task[3] = self.model.current_timestep + 450
                    #check = True
                #if self.task[6] == self.task_station.produce_product['Id_product']:
                #    if self.task_station.inventory.loc[self.task[1]].values[0] < material['use per time'].values[0]:
                #        self.task[3] = self.model.current_timestep - 100
            self.task_station.inventory.loc[self.task[1]] += self.task[4]
            #if check == True:
            #    self.task[3] = self.model.current_timestep + 450
            #    check = False
            self.task_state = 5
            if not len(self.assigned_tasks) > 1:
                #check where in the loop the amr is and if there is a pallet with 
                #finished products ready to be picked up further in the queue
                #if so create a task to pickup 
                if self.task_station.unique_id == self.model.stations[2].unique_id:
                    for i in [0,1,3,4]:
                        task = self.check_buffer_content(i)
                        if task != None:
                            return
                elif self.task_station.unique_id == self.model.stations[0].unique_id:
                    for i in [1,3,4]:
                        task = self.check_buffer_content(i)
                        if task != None:
                            return
                elif (self.task_station.unique_id == self.model.stations[1].unique_id or
                    self.task_station.unique_id == self.model.stations[4].unique_id):
                    for i in [3,4]:
                        task = self.check_buffer_content(i)
                        if task != None:
                            return
                elif self.task_station.unique_id == self.model.stations[3].unique_id:
                    task = self.check_buffer_content(3)
                    return

                
    def pickup(self):
        
        #function to do a pickup of finished products
        self.counter += 1
        #if the amr not in the queue at the station append it and change state
        if self.unique_id not in self.task_station.amr_buffer and self.task_state == 1:
            self.task_station.amr_buffer.append(self.unique_id)
            self.state = [4,1]
        #if the amr at the front of the queue change state and start picking up 
        if self.unique_id in self.task_station.amr_buffer and self.task_state == 1:
            if (self.task_station.amr_buffer.index(self.unique_id) == 0 or 
                self.task_station.amr_buffer.index(self.unique_id) == 1):
                self.counter = 0
                self.task_state = 2
        #if waiter for loading_time time steps at buffer, pickup products
        if self.counter >= self.loading_time and self.task_state == 2:
            self.loaded = 1
            self.task_state = 3
            self.state = [1,1]
            #if products are picked up delete amr from the queue
            del self.task_station.amr_buffer[self.task_station.amr_buffer.index(self.unique_id)]
            check = False
            #if the buffer is not full yet the task is not too late
            if self.task_station.state not in [3,4] and self.task[3] < self.model.current_timestep:
                check = True
            #remove the products from the buffer content
            self.task_station.buffer.loc[self.task[6],0] -= min(self.task[5],self.task_station.buffer.loc[self.task[6],0])
            if self.task not in self.task_station.outstanding_tasks:
                print(self.task)
            #from stations point of view task is finished, so remove from task
            self.task_station.outstanding_tasks.remove(self.task)
            if check == True:
                check = False
                self.task[3] = self.model.current_timestep + 450
    
    def sortby(self,somelist, n):
        sort = True
        if sort == True:
            nlist = [(x[n], x) for x in somelist]
            nlist.sort()
            return [val for (key, val) in nlist]   
        else:
            return somelist
   
    def check_dropofftasks(self):
        
        #check for which station the pickup task is, the stations with the dropoff
        #point for raw materials has to be earlier in the loop
        ids = self.model.stations[0].unique_id
        if self.task[0] == ids:
            self.check_tasks = [3]
        elif self.task[0]  == ids + 1:
            self.check_tasks = [0,3]
        elif self.task[0]  == ids + 3:
            self.check_tasks = [0,1,2,3,4]
        elif self.task[0]  == ids + 4:
            self.check_tasks = [0,1,2,4]
        else:
            return
        #check if there are dropoff tasks for the selected stations which have to be doene
        for k in self.check_tasks:
            #sort the tasks on goal time
            tasks = self.sortby(self.model.stations[k].outstanding_tasks,3)
            #loop over the tasks
            for task in tasks:
                #select only the replenishment tasks
                if task[1] != -1:
                    check = 0
                    #check if no AMR has already assigned that task
                    for i in self.model.AMR:
                        if task not in i.assigned_tasks:
                            check += 1
                    #if no amr is doing the task
                    if check == len(self.model.AMR) : 
                        #set in assigned tasks
                        self.assigned_tasks.appendleft(task)
                        #make it the current task
                        self.task = task
                        #remove the task from the task list to prevent it from being assigned again
                        self.model.task_list.remove(task)
                        self.tasks_created_1 += 1
                        return
                    
        #if no open dropoff tasks in the stations check for upcoming tasks within 
        #the given check time
        for k in self.check_tasks:     
            #loop over tasks in schedule
            for index,value in self.model.stations[k].schedule.iterrows():
                #check if the time is between current timestep and check interval
                if self.model.current_timestep + self.check_time > value[2] and value[2] > self.model.current_timestep:
                    task = value.tolist()
                    for i,j in enumerate(task):
                        if i not in [4]:
                            task[i] = int(j)
                    self.assigned_tasks.appendleft(task)
                    self.model.stations[k].outstanding_tasks.append(task)
                    self.task = task
                    self.model.stations[k].schedule = self.model.stations[k].schedule.drop([index],axis=0)
                    self.model.total_task_list.append(task)
                    self.tasks_created += 1
                    return 
                
    def do_task(self):
        
        #check if there already is a task started
        if self.task == None and len(self.assigned_tasks)>0:
            self.task = self.assigned_tasks[0]
            #if it is a pickup task and the loop_state = 0 which means at the
            #raw materials warehouse
            
            if self.task[1] == -1 and self.loop_state == 0:
                #if there is no replenishment task created yet and the time to finish 
                #the dropoff task is enough to finish 2 tasks 
                if self.check_dropoff == False and self.task[3]-self.model.current_timestep > self.two_task_time:
                    #check if there is a replenishment task possible
                    self.check_dropofftasks()
                    self.check_dropoff = True
            
            self.starttime = self.model.current_timestep
            self.counter = 0
            self.task_state = 0 
            self.start_location = self.location
            self.task_station = self.model.stations[self.task[0]-len(self.model.AMR)-1]
        elif self.task == None:
            return 
        
        #replenishment task
        if self.task[1] != -1 and self.task[1] != -2:
            #location of the raw materials of the station
            self.task_location = self.task_station.queue_location
            if self.loop_state == 0:
                #move to the raw material warehouse
                self.move(self.warehouse_inf[0])
                #check if arrived at the raw materials warehouse, if so start picking up
                if sum(self.location == self.warehouse_inf[0]) == 2:
                    self.task_state = 1
                    self.counter += 1
                    #if materials picked up in warehouse continue loop and change task state
                    if self.counter >= self.loading_time and self.task_state == 1:
                        self.loaded = 1
                        self.task_state = 2
                        self.loop_state = 1
            #check the progress of the loop
            elif self.loop_state == 1:
                #check the state of the task and move to the next point in the loop
                if self.task_state in [2,5]:
                    self.move(self.route[0])
                #if the location after movement is the same as the task location
                #change the state of the task
                if sum(self.location == self.task_location) == 2 and self.task_state == 2:
                    self.counter = 0
                    self.task_state = 3
                #check the state of the task and call the dropoff function
                elif self.task_state in [3,4]:
                    self.dropoff() 
                #check if the next point of the loop is reached and change 
                #the state of the loop to go to the next point in the loop
                if sum(self.location == self.route[0]) == 2:
                    self.loop_state = 2
            elif self.loop_state == 2:
                if self.task_state in [2,5]:
                    self.move(self.route[1])
                if sum(self.location == self.task_location) == 2 and self.task_state == 2:
                    self.counter = 0
                    self.task_state = 3
                elif self.task_state not in [0,1,2,5]:
                    self.dropoff()
                if sum(self.location == self.route[1]) == 2:
                    self.loop_state = 3
            elif self.loop_state == 3:
                if self.task_state in [2,5]:
                    self.move(self.route[2])
                if sum(self.location == self.task_location) == 2 and self.task_state == 2:
                    self.counter = 0
                    self.task_state = 3
                elif self.task_state not in [0,1,2,5]:
                    self.dropoff()
                if sum(self.location == self.route[2]) == 2:
                    self.loop_state = 4
            elif self.loop_state == 4:
                if self.task_state in [2,5]:
                    self.move(self.warehouse_inf[0])
                if sum(self.location == self.task_location) == 2 and self.task_state == 2:
                    self.counter = 0
                    self.task_state = 3
                elif self.task_state not in [0,1,2,5]:
                    self.dropoff()
                if sum(self.location == self.warehouse_inf[0]) == 2:
                    self.loop_state = 0
        
        #pick up task
        else:
            #location of the finished products at the station
            self.task_location = self.task_station.buffer_location
            if self.loop_state == 0:
                #move to the raw materials warehouse to start the loop
                self.move(self.warehouse_inf[0])
                if sum(self.location == self.warehouse_inf[0]) == 2:
                    self.task_state = 0
                    self.counter += 1
                    self.loop_state = 1
            #check the state of the loop
            elif self.loop_state == 1:
                #check the state of the task and move to the next point of the loop
                if self.task_state in [0,3]:
                    self.move(self.route[0])
                #if the station is reached change the task state
                if sum(self.location == self.task_location) == 2 and self.task_state == 0:
                    self.counter = 0
                    self.task_state = 1   
                #check the task state and call pickup function
                elif self.task_state in [1,2]:
                    self.pickup()
                 #check if the next point of the loop is reached and change 
                 #the state of the loop to go to the next point in the loop
                if sum(self.location == self.route[0]) == 2:
                    self.loop_state = 2
            elif self.loop_state == 2:
                if self.task_state in [0,3]:
                    self.move(self.route[1])
                if sum(self.location == self.task_location) == 2 and self.task_state == 0:
                    self.counter = 0
                    self.task_state = 1   
                elif self.task_state != 0:
                    self.pickup()
                if sum(self.location == self.route[1]) == 2:
                    self.loop_state = 3
            elif self.loop_state == 3:
                if self.task_state in [0,3]:
                    self.move(self.route[2])
                if sum(self.location == self.task_location) == 2 and self.task_state == 0:
                    self.counter = 0
                    self.task_state = 1   
                elif self.task_state != 0:
                    self.pickup()
                if sum(self.location == self.route[2]) == 2:
                    self.loop_state = 4
            elif self.loop_state == 4:
                if self.task_state in [0,3]:
                    self.move(self.warehouse_inf[1])
                if sum(self.location == self.warehouse_inf[1] ) == 2 and self.task_state == 0:
                    self.counter = 0
                    self.task_state = 1   
                elif self.task_state in [1,2]:
                    self.pickup()
                #check if amr arrived at the warehouse after this step, 
                #change task state and start unloading the pallet
                if sum(self.location == self.warehouse_inf[1]) == 2 and self.task_state == 3:
                    self.counter = 0
                    self.task_state = 4
                if self.task_state == 4 and self.counter <= self.loading_time:
                    self.counter += 1 
                #unload the pallet in loading_time seconds and change the state to continue the loop
                elif self.counter >= self.loading_time and self.task_state == 4:
                    self.loaded = 0
                    self.task_state = 5
                #if the task is finished change the loop state to 0 again to start a new loop
                if sum(self.location == self.warehouse_inf[1]) == 2 and self.task_state == 5:
                    self.loop_state = 0
                    self.check_dropoff = False
        
        #check if task is finished or if replenishment task and new pickup task created
        #to do in this loop, then continue with the pickup task
        if (self.task != None and self.task_state == 5 and self.loop_state == 0 
            or self.created == True and self.task_state == 5 and self.task != None):
            #store start, finish time, time to complete the task, if it is too late how much
            self.task[7] = self.starttime
            self.task[8] = self.model.current_timestep
            self.task[9] =  self.task[8] - self.task[7]
            if (self.task[8] - self.task[3]) > 0:
                self.task[10] = int(self.task[8] - self.task[3])
            self.task[11] = self.unique_id - 1
            self.task = None
            self.state = [0,1]
            self.task_state = -1
            self.assigned_tasks.popleft()
            self.starttime = 0
            self.created = False
            self.check_battery()
            
    def create_task(self,station_id,material_id,release,finish_time,amount,ulcycle,product):
        
        #function that creates a task
        task = [station_id,material_id,release,finish_time,amount,ulcycle,product,0,0,0,0,0]
        self.model.total_task_list.append(task)
        return task
    
    def step(self):
        
        self.check_battery()
        if self.batterylife < 0:
            print('battery smaller than 0',self.unique_id)
            sys.exit('simulation stopped because battery smaller than 0')
        self.update_state()
        #if not charging than can do a task and use battery
        if self.state[0] != 2 and self.state[0] != 3:
            self.batterylife -= 1
            self.do_task()
        if self.model.total_task_list == None:
            sys.exit('nonetype in amr')


