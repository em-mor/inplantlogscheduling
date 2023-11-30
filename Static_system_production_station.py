from mesa import Agent
from collections import deque
import numpy as np
import pandas as pd
import math
import copy

class ProductionStation(Agent):
    
    def __init__(self,unique_id,model,station_inf,product_inf
                 ,production_list,raw_mat_inf,warmup):
        
        super().__init__(unique_id,model)
        self.state = 1
        self.buffer_cap_pallet = product_inf[2]
        self.buffer_cap = [0 for x in range(len(production_list))]
        self.speed = product_inf[1] / (16*60*60)
        self.scheduled_pallets = [0]
        self.buffer_location = np.array([station_inf[0],station_inf[1]])
        self.queue_location = np.array([station_inf[2],station_inf[3]])
        self.outstanding_tasks = deque()
        self.finish_time = 0
        self.counter = [0]
        keys = pd.Index(range(len(production_list)))
        self.production_list = production_list.set_index(keys)
        self.raw_mat_inf = pd.DataFrame()
        self.produce_product = pd.DataFrame()
        self.raw_mat = pd.DataFrame()
        self.amount_produced = 0
        self.total = 0
        self.amr_queue = deque()
        self.amr_buffer = deque()
        self.task_time = 900
        self.production_index = 0
        self.time = []
        self.warmup = warmup
        self.threshold = product_inf[3]
        self.finish = 0
        
        for row in self.production_list.to_numpy():
            product = row[0]
            materials = raw_mat_inf.loc[(raw_mat_inf['Padre'] == product)]
            self.raw_mat_inf = self.raw_mat_inf.append(materials)
        schedule_finish_time = []
        schedule_start_time = [0]
        
        #create the production schedule
        for index,row in self.production_list.iterrows():
            if index > 0:
                schedule_start_time.append(schedule_finish_time[-1])
                schedule_finish_time.append(schedule_finish_time[-1]+
                                        int(1/self.speed*row['# Unit loads']))
            elif index == 0:
                schedule_finish_time.append(int(1/self.speed*row['# Unit loads'])+self.warmup)
            self.buffer_cap[index] = self.buffer_cap_pallet*row['# UL/cycle']
        self.production_list.loc[:,'start_time'] = schedule_start_time    
        self.production_list.loc[:,'finish_time'] = schedule_finish_time
        self.raw_mat_inf = self.modify_raw_mat(copy.copy(self.raw_mat_inf))
        
        #create the production schedule of tasks
        self.schedule = []
        for row in self.raw_mat_inf.to_numpy():
            product = self.production_list.loc[(self.production_list['Id_product']==row[1])] #padre
            for i in range(row[12]): #pallets
                if product.index.values[0] != 0:
                    finish_time = (product['start_time']).values[0] - self.task_time + row[13]*i #reorder time
                elif product.index.values[0] == 0:
                    if i == 0:
                        finish_time = (product['start_time']).values[0] #reorder time
                    elif i > 0:
                        finish_time = (product['start_time'] + self.warmup).values[0] + row[13]*i #reorder time
                amount = min(row[9],row[11]) #material needed
                material = row[3] #component
                release = finish_time - self.task_time
                task = self.create_task(self.unique_id,material,release,finish_time,
                                        amount,product['# UL/cycle'].values[0],row[1])
                self.schedule.append(task)
        self.schedule = pd.DataFrame(self.schedule)
        self.schedule.columns = ['Production station', 'material id','release time', 
                                 'goal time','amount', 'Ul/cycle','product id',
                                 'start time', 'finish time','total time','latency','amr']
        self.schedule['release time'] += self.task_time + 1
        self.schedule['goal time'] += self.task_time + 1
        self.schedule = self.schedule.sort_values(by=['release time'])
        
        keys = self.raw_mat_inf['Componente']
        keys = keys.drop_duplicates(keep='first', inplace=False)
        self.inventory = pd.DataFrame([0 for x in range(len(keys))])
        self.inventory = self.inventory.set_index(keys)
        
        keys = self.production_list['Id_product']
        self.buffer = pd.DataFrame([0 for x in range(len(production_list))])
        self.buffer = self.buffer.set_index(keys)
        
    def create_task(self,station_id,material_id,release,finish_time,amount,ulcycle,product):
        
        #function that creates a task
        task = [station_id,material_id,release,finish_time,amount,ulcycle,product,0,0,0,0,0]
        return task

    def stop_production(self):
        
        check = [0 for x in range(len(self.raw_mat))]
        counter = 0 
        #check if there is still raw materials left to produce current product batch
        for row in self.raw_mat.to_numpy():
            if self.inventory.loc[row[3]].values[0] > row[14]:
                check[counter] = 1
            counter += 1
        #if the buffer is full AND the raw materials are empty
        if (sum(self.buffer[0]) + self.speed > self.buffer_cap_pallet 
            and sum(check) != len(self.raw_mat)):
            self.state = 4
        #elif the buffer is full
        elif sum(self.buffer[0]) + self.speed > self.buffer_cap_pallet:
            self.state = 3
            tasks_created = 0
            #loop over the buffer content
            for index,content in self.buffer.iterrows():
                #if there are pallets ready to pickup create pickup tasks
                if content[0] > 0:
                    product = self.production_list.loc[(self.production_list['Id_product']==index)]
                    ulcycle = product['# UL/cycle'].values[0]
                    for i in range(int(content[0]/ulcycle)):
                        release = self.model.current_timestep
                        finish_time = self.model.current_timestep
                        amount = i
                        task = self.create_task(self.unique_id,-1,release,finish_time,amount,
                                                ulcycle,product['Id_product'].values[0])
                        self.outstanding_tasks.append(task)
                        self.model.task_list.append(task)
                        self.model.total_task_list.append(task)
                        tasks_created += 1
                        if tasks_created > int(self.threshold*self.buffer_cap_pallet):
                            return
        #elif the raw materials are empty
        elif sum(check) != len(self.raw_mat):
            self.state = 1
    
    def production(self):
        
        #start production only after the warmup time
        if self.model.current_timestep < self.warmup:
            return 
        #check if enough materials in the queue and the buffer is not full while producing
        if (self.state == 0 and sum(self.buffer[0]) < (self.buffer_cap_pallet+self.speed)
            and len(self.produce_product) > 0): 
            check = [0 for x in range(len(self.raw_mat))]
            counter = 0
            for row in self.raw_mat.to_numpy():
                if self.inventory.loc[row[3]].values[0] > row[14]:
                    check[counter] = 1
                counter += 1
            if sum(check) == len(self.raw_mat):
                self.buffer.loc[self.produce_product['Id_product']] += self.speed
                self.amount_produced += self.speed
                self.total += self.speed
                #remove the raw materials from the pallets
                for row in self.raw_mat.to_numpy():
                    self.inventory.loc[row[3]] -= row[14]
            else: 
                self.stop_production()
        #if the buffer with finished products is full or at least one of the raw
        #materials is empty stop the production
        elif self.state == 0:
            self.stop_production()
        #check if materials arrived or buffer got emptied, if so start production
        if not self.produce_product.empty:
            if self.state in [1,3,4] and sum(self.buffer[0]) < self.buffer_cap_pallet-self.speed: 
                check = [0 for x in range(len(self.raw_mat))]
                counter = 0
                for row in self.raw_mat.to_numpy():
                    if self.inventory.loc[row[3]].values[0] > row[14]:
                        check[counter] = 1
                    counter += 1
                if sum(check) == len(self.raw_mat):
                    self.state = 0
            #if current product batch is finished
            if self.amount_produced >= self.produce_product['# Unit loads']:
                self.produce_product = pd.DataFrame()
    
    def follow_schedule(self):
          
        #loop over schedule
        for row in self.schedule.to_numpy():
            #if release time of task is reached, append it to central the task list
            if self.model.current_timestep == row[2]:
                task = row.tolist()
                for i,j in enumerate(task):
                    if i not in [4]:
                        task[i] = int(j)
                self.model.task_list.append(task)
                self.model.total_task_list.append(task)
                self.outstanding_tasks.append(task)  
            #if the current timestep is smaller then the release time there are no more
            #tasks ready to be released because these are sorted on release time
            elif self.model.current_timestep <= row[2]:
                break
        #if no product batch in production and still products need to be produced
        #go to the next product batch
        if self.produce_product.empty and len(self.production_list) > self.production_index:
            if self.model.current_timestep > self.production_list.loc[self.production_index,'start_time']:
                self.produce_product = self.production_list.iloc[self.production_index]
                self.raw_mat = self.raw_mat_inf.loc[self.produce_product['Id_product'] 
                                                == self.raw_mat_inf['Padre']]
                #increase the production index and set amount of this product to 0
                self.production_index += 1
                self.amount_produced = 0
        elif (self.produce_product.empty and len(self.production_list) == self.production_index 
              and self.state != 2):
            self.state = 2
            self.finish = self.model.current_timestep-self.warmup
            print('production at station',self.unique_id,'is finished at', self.model.current_timestep-self.warmup)
            
    def modify_raw_mat(self,raw_mat):
        
        #function that adds the amount, # of pallets, reorder time and use per
        #timestep of each rawmaterial to the dataframe
        pallets = []
        time = []
        material = []
        use = []
        
        for row in raw_mat.to_numpy():
            product = self.production_list.loc[(self.production_list['Id_product']==row[1])]
            if product.index != 0:
                producing_time = (product['finish_time'] - product['start_time']).values
            else:
                producing_time = (product['finish_time'] - self.warmup).values
            use.append((float(row[5]/row[7]*product['# units'])/producing_time)[0])
            material.append(np.ceil(((float(row[5]/row[7])*product['# units']).values)[0])+2*use[-1])
            pallets.append(math.ceil(material[-1]/row[9]))
            reorder_time = math.floor(producing_time/math.ceil(pallets[-1]))
            if reorder_time == producing_time:
                reorder_time = 0
            time.append(reorder_time)
        #add the total amount of each material needed for producing the amount of products
        raw_mat.loc[:,'material needed'] = material
        #add the amount of pallets of this material needed
        raw_mat.loc[:,'pallets'] = pallets
        #add the time to replenish each material
        raw_mat.loc[:,'reorder time'] = time
        #add the use of each material per time step
        raw_mat.loc[:,'use per time'] = use
        #reassign the indeces of the dataframe
        keys = pd.Index(range(len(raw_mat)))
        raw_mat = raw_mat.set_index(keys)
        return raw_mat
    
    def step(self):
        
        #check if there is production at a station, if not print this
        if self.model.current_timestep == 1 and self.production_list.empty:
            self.state = 2
            print('no production at station',self.unique_id)
        self.follow_schedule()
        self.production()

