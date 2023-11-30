from mesa import Agent
from collections import deque
import numpy as np

class chargingstation(Agent): 
    #charging station class
    
    def __init__(self,unique_id,model,charging_inf):
        
        super().__init__(unique_id,model)
        self.queue = deque()
        self.location = np.array([charging_inf[0],charging_inf[1]])

    def step(self):
        
        #check if there is an amr at the charging station
        if len(self.queue)>0:
            #select the first AMR to charge
            charging_amr = self.queue[0]
            #increase batterylife by charging
            charging_amr.batterylife += charging_amr.charging_speed
            #if fully charged delete from charging queue and change state
            if charging_amr.batterylife >= 36000: 
                if charging_amr.batterylife > 36000:
                    charging_amr.batterylife = 36000
                #delete the charged AMR from the queue and change the state
                self.queue.popleft()
                charging_amr.state = [0,1]
                charging_amr.chosen_charging_idx = -1
                #charging_amr.battery_counter = 0