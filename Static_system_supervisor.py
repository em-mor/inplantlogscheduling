from mesa import Agent

class Supervisor(Agent):
    
    #supervisor agent, assigns the tasks to the amrs
    def __init__(self,unique_id,Model):
        
        super().__init__(unique_id, Model)

    def step(self):
        
        #function that assigns a task to an idle amr
        assigned_tasks = []
        #loop over task list
        for i in self.model.task_list:
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