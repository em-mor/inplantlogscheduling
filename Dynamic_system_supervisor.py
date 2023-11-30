from mesa import Agent
import sys

class Supervisor(Agent):
    
    #supervisor agent, assigns the tasks to the amrs
    def __init__(self,unique_id,Model):
        
        super().__init__(unique_id, Model)

    def sortby(self,somelist, n):
        sort = True
        if sort == True:
            nlist = [(x[n], x) for x in somelist]
            nlist.sort()
            return [val for (key, val) in nlist]   
        else:
            return somelist
    
    def step(self):
        
        #function that assigns a task to an idle amr
        assigned_tasks = []
        # sort task list on goal time, so task wich has to be finished earlier
        # will be assigned earlier
        sorted_list = self.sortby(self.model.task_list,3)
        #loop over task list
        for i in sorted_list:
            #loop over all amrs
            for amr in self.model.AMR:
                #check if the amr has a task assigned or not
                if (len(amr.assigned_tasks) == 0 and amr.state[0] == 0 
                    and amr.batterylife > 9000):
                    #if not assign the current task
                    amr.assigned_tasks.append(i)
                    #append the assigned task to the list
                    assigned_tasks.append(i)
                    #continue with the next task
                    break
        #remove the assigned tasks from the task list
        for j in assigned_tasks:
            self.model.task_list.remove(j)
            