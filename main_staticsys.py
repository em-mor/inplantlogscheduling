from mesa import Model
from collections import deque
import time
import pandas as pd
import numpy as np
from simresults import SimResults
from charging_station import chargingstation
from amr import AMR
from production_station import ProductionStation
from supervisor import Supervisor

class ProductionModel(Model):
    
    def __init__(self,timesteps,no_AMR,station_inf,product_inf,charging_inf
                 ,warehouse_inf,production_list,raw_mat_inf,real_prod,
                 total_task_list,closed_loop_route,warmup):
        self.timesteps = timesteps
        self.current_timestep = 1
        self.task_list = deque([])
        #create AMRs, production stations and charging stations
        self.AMR = []
        self.stations = []
        self.charging_stations = []
        self.id = 0
        self.total_task_list = total_task_list
        self.Supervisor = Supervisor(self.id,self)
        for i in range(1,no_AMR+1):
            amr = AMR(self.id+i,self,warehouse_inf,closed_loop_route)
            self.AMR.append(amr)
        self.id += i
        for i in range(1,len(station_inf)+1):
            station = ProductionStation(self.id+i,self,station_inf[i-1],product_inf[i-1]
                                        ,production_list[i-1],raw_mat_inf,warmup)
            self.stations.append(station)
        self.id += i
        for i in range(1,len(charging_inf)+1):
            charging = chargingstation(self.id+i,self,charging_inf[i-1])
            self.charging_stations.append(charging)
        self.id += i
        #process results
        self.results = SimResults(self.id+1,self)
        
    def step(self):
        
        amr = self.AMR[0]
        self.Supervisor.step()
        for station in self.stations:
            station.step()
        for amr in self.AMR:
            amr.step()
        for charging_station in self.charging_stations:
            charging_station.step()  
        self.results.step()
        self.current_timestep += 1
        #if self.current_timestep % 10000 == 0:
        #    print(self.current_timestep)
        
#define input for the simulation
production = pd.read_excel('production_mod1.xlsx')
bom = pd.read_excel('bom_mod.xlsx')
day_production = pd.read_excel('day_production.xlsx')
date = day_production.iloc[207]
real_prod = production.loc[production['Data'] == date.iloc[0]]

raw_mat_inf = pd.DataFrame()
for index,row in real_prod.iterrows():
    raw_mat = bom.loc[bom['Padre'] == row['Id_product']]
    if row['Id_product'] not in raw_mat_inf.values:
        raw_mat_inf = raw_mat_inf.append(raw_mat)

production_list = [0]*5
for key,value in enumerate(production_list):
    production_list[key] = real_prod.loc[real_prod['station'] == key]

#Model variables
warmup = 4800 
timesteps = 57600 + warmup
no_AMR = 8
size = 1
buffer_pickup_threshold = 0.9
station_inf = [(30,105,50,105),(50,105,100,105),(60,75,35,80),(90,60,105,60),(115,60,115,105)]
product_inf = [(79,167, 10*size, buffer_pickup_threshold ),
               (27,69,  4*size , buffer_pickup_threshold ),
               (62,149, 9*size , buffer_pickup_threshold ),
               (9,21,   3*size , buffer_pickup_threshold ),
               (30,101, 6*size , buffer_pickup_threshold )]
closed_loop_route = [(60,80),(30,105),(115,60)]
charging_inf = [(95,60),(100,60),(95,60),(100,60),(95,60),(100,60)]
warehouse_inf = [(30,55),(90,45)]

#define number of runs
nrRuns = 1

#define lists to store the results of the simulations
avg_time = [0 for x in range(nrRuns)]
too_late = [0 for x in range(nrRuns)]
avg_pickup = [0 for x in range(nrRuns)]
avg_replenish = [0 for x in range(nrRuns)]
state_time = [0 for x in range(nrRuns)]
station_state_time = [0 for x in range(nrRuns)]
total_length = [0 for x in range(nrRuns)]
state_over_time = [0 for x in range(nrRuns)]
station_over_time = [0 for x in range(nrRuns)]
df = [0 for x in range(nrRuns)]
model = [0 for x in range(nrRuns)]
station_states = [0 for x in range(nrRuns)]
amr_states = [0 for x in range(nrRuns)]
amr_state_over_time = [0 for x in range(nrRuns)]
station_state_over_time = [0 for x in range(nrRuns)]
total = [0 for x in range(nrRuns)]
loaded_time = [0 for x in range(nrRuns)]
load_time = [0 for x in range(nrRuns)]
finish = [0 for x in range(nrRuns)]

for k in range(nrRuns):
    total_task_list = []
    model[k] = ProductionModel(timesteps,no_AMR,station_inf,product_inf,charging_inf
                            ,warehouse_inf,production_list,raw_mat_inf,real_prod,
                            total_task_list,closed_loop_route,warmup)
    t1 = time.time()
    for i in range(timesteps):
        model[k].step()
    t2 = time.time()
    print("simulaiton time: " , (t2-t1))
    
    total[k] = [0 for x in range(len(model[k].stations))]
    finish[k] = [0 for x in range(len(model[k].stations))] 
    for i in range(len(model[k].stations)):
        total[k][i] += model[k].stations[i].total
        finish[k][i] = model[k].stations[i].finish
    
    df[k] = pd.DataFrame(total_task_list)
    df[k].columns = ['Production station', 'raw material', 'release', 'goal time','amount',
             'Ul/cycle','product','start time', 'finish time','total time','latency','amr']
    (state_time[k],station_state_time[k],total_length[k],state_over_time[k],
     station_over_time[k],loaded_time[k]) = model[k].results.plot(df[k],False)
    
    amr_state_over_time[k] = [0 for x in range(len(state_over_time[k]))]
    for i in range(len(state_over_time[k])):
        amr_state_over_time[k][i] = pd.DataFrame(state_over_time[k][i]).T
        amr_state_over_time[k][i].columns = ['Idle','Busy','Charging','waiting','Broken']
    
    station_state_over_time[k] = [0 for x in range(len(station_over_time[k]))]
    for i in range(len(station_over_time[k])):
        station_state_over_time[k][i] = pd.DataFrame(station_over_time[k][i]).T
        station_state_over_time[k][i].columns = ['Busy','No Raw Materials','Finished',
                                  'Buffer full','Buffer full and no Raw Materials']
    for i,j in enumerate(loaded_time[k]):
        loaded_time[k][i] = j[warmup:]
    load_time[k] = sum(sum(loaded_time[k][x]) for x in range(len(loaded_time[k])))
    
    warmup_check = True
    if warmup_check == True:
        df[k] = df[k].loc[df[k]['release'] >= warmup]
        for i in range(len(station_state_time[k])):
            station_state_over_time[k][i]['Busy'] -= station_state_over_time[k][i].loc[warmup,'Busy']
            station_state_over_time[k][i]['No Raw Materials'] -= station_state_over_time[k][i].loc[warmup,'No Raw Materials']
            station_state_over_time[k][i]['Finished'] -= station_state_over_time[k][i].loc[warmup,'Finished']
            station_state_over_time[k][i]['Buffer full'] -= station_state_over_time[k][i].loc[warmup,'Buffer full']
            station_state_over_time[k][i]['Buffer full and no Raw Materials'] -= station_state_over_time[k][i].loc[warmup,'Buffer full and no Raw Materials']
            station_state_over_time[k][i] = station_state_over_time[k][i][warmup:]
        for i in range(len(state_time[k])):
            amr_state_over_time[k][i]['Idle'] -= amr_state_over_time[k][i].loc[warmup,'Idle']
            amr_state_over_time[k][i]['Busy'] -= amr_state_over_time[k][i].loc[warmup,'Busy']
            amr_state_over_time[k][i]['Charging'] -= amr_state_over_time[k][i].loc[warmup,'Charging']
            amr_state_over_time[k][i]['waiting'] -= amr_state_over_time[k][i].loc[warmup,'waiting']
            amr_state_over_time[k][i]['Broken'] -= amr_state_over_time[k][i].loc[warmup,'Broken']
            amr_state_over_time[k][i] = amr_state_over_time[k][i][warmup:]
        
        #% of time all production stations spend in each state
        station_states[k] = [0 for x in range(len(station_state_time[k]))]
        for i in station_state_over_time[k]:
            for j in range(len(station_states[k])):
                station_states[k][j] += i.iloc[-1,j]
        
        #% of time all amrs are in each state
        amr_states[k] = [0 for x in range(5)]
        for i in amr_state_over_time[k]:
            for j in range(5):
                amr_states[k][j] += i.iloc[-1,j]
                
        avg_time[k] = np.mean(df[k]['total time'])
        avg_pickup[k] = np.mean(df[k].loc[(df[k]['raw material'] == -1) | (df[k]['raw material'] == -2)]['total time'])
        avg_replenish[k] = np.mean(df[k].loc[(df[k]['raw material'] != -1) & (df[k]['raw material'] != -2)]['total time'])
        too_late[k] = len(df[k].loc[(df[k]['latency']>0)])/len(df[k])*100

#write results to excel
amr_states = pd.DataFrame(amr_states)
amr_states.columns = ['Idle','Busy','Charging','Waiting','Broken']
station_states = pd.DataFrame(station_states)
station_states.columns = ['Busy','No Raw Materials','Finished','Buffer full',
                        'Buffer full and no Raw Materials']    
averages = [0 for x in range(5)]
averages[0] = np.mean(amr_states['Idle'])
averages[1] = np.mean(amr_states['Busy'])
averages[2] = np.mean(amr_states['Charging'])
averages[3] = np.mean(amr_states['Waiting'])
averages[4] = np.mean(amr_states['Broken'])
avg = pd.DataFrame(averages).T
avg.columns = ['Idle','Busy','Charging','Waiting','Broken']
amr_states = amr_states.append(avg)

averages = [0 for x in range(5)]
averages[0] = np.mean(station_states['Busy'])
averages[1] = np.mean(station_states['No Raw Materials'])
averages[2] = np.mean(station_states['Finished'])
averages[3] = np.mean(station_states['Buffer full'])
averages[4] = np.mean(station_states['Buffer full and no Raw Materials'])
avg = pd.DataFrame(averages).T
avg.columns = ['Busy','No Raw Materials','Finished','Buffer full',
                        'Buffer full and no Raw Materials']
station_states = station_states.append(avg)

times = pd.DataFrame()
times['avg_time'] = avg_time
times['avg_pickup'] = avg_pickup
times['avg_replenish'] = avg_replenish
times['too_late'] = too_late
times['load_time'] = load_time

averages = [0 for x in range(5)]
averages[0] = np.mean(times['avg_time'])
averages[1] = np.mean(times['avg_pickup'])
averages[2] = np.mean(times['avg_replenish'])
averages[3] = np.mean(times['too_late'])
averages[4] = np.mean(times['load_time'])
avg = pd.DataFrame(averages).T
avg.columns = ['avg_time','avg_pickup','avg_replenish','too_late','load_time']
times = times.append(avg)

total_length = pd.DataFrame(total_length).T

finish_time = pd.DataFrame(finish).T
total_prod = pd.DataFrame(total).T

parameters = [no_AMR, warmup, size, buffer_pickup_threshold]
parameters = pd.DataFrame(parameters)

with pd.ExcelWriter(f"Base_output{buffer_pickup_threshold}.xlsx") as writer:
    amr_states.to_excel(writer, sheet_name="amr_states",index=False)
    station_states.to_excel(writer, sheet_name='station_states',index=False)
    total_length.to_excel(writer, sheet_name='queue',index=False)
    times.to_excel(writer, sheet_name='times',index=False)
    finish_time.to_excel(writer, sheet_name='finish', index=False)
    total_prod.to_excel(writer, sheet_name='total', index=False)
    parameters.to_excel(writer, sheet_name='parameters', index=False)