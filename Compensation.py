from datetime import *
from dateutil.relativedelta import *
from BaseProjections.Constants import *
import pandas as pd

class CCompensation():

    def __init__(self, inputs, filenames, employees, journal_entry, formats, rev_expense_log):

        people, comp, comp_accounts, cap_accounts, excel_file = filenames

        #'Excel file for employees'
        #'Employees' tab 
        #'Comp' tab
        #'CompAccounts' tab

        #    or

        #'Excel file for contractors'
        #'Contractors' tab
        #'Contractors_comp' tab
        #'Contractors_accounts' tab    

        xls = inputs.full_path_input + excel_file
        
        self.Employee_dict = {}
        self.employee_df = pd.DataFrame()
        self.capsw_df = pd.DataFrame()
        self.inputs = inputs

        self.capSW_dict = {}
        self.employee_capSW_dict = {}
        self.contractors_capSW_dict = {}
        self.transaction_log_employees = []
        self.transaction_log_contractors = []
        self.transaction_log = []
        self.journal_entry = journal_entry
        self.rev_explog_employees = False
        self.rev_explog_contractors = False

        if people == kEmplPeople:
            self.rev_explog_employees = rev_expense_log
        elif people == kContPeople:
            self.rev_explog_contractors = rev_expense_log
        else:
            Print("Error in data sent to Comp module: ", people)
            return

        #default CR account
        self.CR_acct = inputs.cash_account

        try:

            df = pd.read_excel(xls, people)
            self.Employees = df.values.tolist()

            df = pd.read_excel(xls, comp) 
            self.Comp = df.values.tolist()
            self.CompIndx = self.getIndexes(self.Comp)

            df = pd.read_excel(xls, comp_accounts) 
            self.CompAccounts = df.values.tolist()
            self.CompAccountsIndx = self.getIndexes(self.CompAccounts)
                
            TB_file = inputs.full_path_input + kTB_file
            current_TB = inputs.projections_date.strftime("%Y-%m")
            xls = pd.ExcelFile(TB_file)
            df = pd.read_excel(xls, current_TB, header = None)
            closing_TB = df.values.tolist()
            closing_TBIndx = self.getIndexes(closing_TB)

            # go thru each employee or contractor 
            emply_num = 0

            #list comprehension needed
            for employee_row in self.Employees:

                employee_instance =  CEmployee_expenses(employee_row, self.Comp, inputs, emply_num)
                self.Employee_dict[employee_instance.empl_num]  = employee_instance
                self.employee_df = pd.concat([self.employee_df, pd.DataFrame([employee_instance.total_employee_comp])], ignore_index=True)
                self.capsw_df = pd.concat([self.capsw_df, pd.DataFrame([employee_instance.cap_sw_comp])], ignore_index=True)
                emply_num +=1 
    

        except FileNotFoundError:
            print("Can't find or one or more compensation file(s) ")


        if people == kEmplPeople :

            self.capSW_dict[people] = self.employee_df
            self.capSW_dict[people+kCapSWCompString] = self.capsw_df
            self.capSW_dict[kCapSWTotals] = self.capsw_df.sum(axis = 0)
            self.write_CompSW(kCapSWComp, inputs)

        elif people == kContPeople:
            self.capSW_dict[people] = self.employee_df
            self.capSW_dict[people+kCapSWCompString] = self.capsw_df
            self.capSW_dict[kCapSWTotals] = self.capsw_df.sum(axis = 0)
            self.write_CompSW(kCapSWCont, inputs)

        else:
            print("Error, compensation type of workers not defined")

    def CCompensationAddMonthsTransactions(self, month, TB, CapSW_CR, people):

        Expense_index = []
        self.totalmonthexpenses = 0

        for employee_key in self.Employee_dict:

            employee = self.Employee_dict[employee_key]
            employee_dept = employee.dept
            
            for employee_expense_key in employee.employee_expenses:

                #fix this for CapSW
                expense_index = self.CompIndx.index(employee_expense_key)
                account_column_row_num = int(self.Comp[expense_index][kCompTypeRowIndex])
                expense_row = self.CompAccountsIndx.index(employee_dept)
                DR_acct = self.CompAccounts[expense_row][account_column_row_num]

                #this is wrong and s/b moved to CapSW class
                if (CapSW_CR == "CapSW") or (CapSW_CR == "CapSWAmort"):
                    CR_acct = self.CompAccounts[expense_row][account_column_row_num]
                else:
                    CR_acct = self.CR_acct
                # else use the default cash account as CR, set above in _init, from inputs
                    
                amount = employee.employee_expenses[employee_expense_key][month]

                self.journal_entry.performJE(month, TB, DR_acct, CR_acct, amount)

                #print ("Testing logging: ", self.rev_explog_employees, self.rev_explog_contractors, people)
                if (self.rev_explog_employees or self.rev_explog_contractors):
                    log_date = self.inputs.get_date(month)
                    log_list = [log_date, DR_acct, CR_acct, amount]
                    self.transaction_log.append(log_list)

                    #if people == kEmplPeople:
                        #self.transaction_log_employees.append(log_list)
                        #print("Employee")
                    #elif people == kContPeople:
                        #self.transaction_log_contractors.append(log_list)
                        #print("Contractor")
                    #else:
                        #print("Error in data sent to Comp module: ", people)
                        #return

        #print(self.transaction_log_employees)
        #print(self.transaction_log_contractors)
        return TB

    def getIndexes(self, Comp):

        Indexes = []
        for comp_row in Comp:
                Indexes.append(comp_row[kFirst])
        return Indexes 

    def write_CompSW(self, filename, inputs):

        writer = pd.ExcelWriter(inputs.full_path_output + filename, engine = 'xlsxwriter')

        for key in self.capSW_dict:
            df = self.capSW_dict[key]
            df.to_excel(writer, sheet_name = key, index = False)

        writer.close()   

class CEmployee_expenses():


    def __init__(self, employee_info, Comp, inputs, emply_num):


        dates = inputs.dates
        self.employee_expenses= {}
        self.employee_comp_list = []
        
        self.empl_num = employee_info[kCompNumIndex]
        self.dept = employee_info[kCompDeptIndex]
        self.name = employee_info[kCompNameIndex]
        
        zero_expenses = [0 for i in range(dates.model_term)]
        total_comp = zero_expenses.copy()

        for comp_row in Comp:

            # self.Comp MUST be run before any of the taxes are run (as they are dependent upon the result)
            # CapSW must be run last, as it is the accumulation of all employee expenses

            #these s/b all changed to constants
            # !!!!!!!!!!!!

            if comp_row[kCompTypeIndex] == "Compensation":
                temp_result = self.Employee_Comp(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))

            elif comp_row[kCompTypeIndex] == "Bonus":
                temp_result = self.Bonus(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "Vacation":
                temp_result  = self.Vacation(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp =list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "FICA":
                temp_result  = self.FICA(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "Medicare":
                temp_result  = self.Medicare(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "FUTA":
                temp_result  = self.FUTA(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "SUI":
                temp_result  = self.SUI(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "Health":
                temp_result  = self.Health(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "WC":
                temp_result  = self.WC(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "EmplSetup":
                temp_result  = self.EmplSetup(employee_info, zero_expenses, inputs)
                self.employee_expenses[comp_row[kCompTypeIndex]] = temp_result
                total_comp = list(map(sum, zip(total_comp, temp_result)))
                
            elif comp_row[kCompTypeIndex] == "CapSW":
                pass

            elif comp_row[kCompTypeIndex] == "CapSWAmort":
                pass
            else:
                print(f"Invalid Comp Type: {comp_row[kCompTypeIndex]}")
           
        cap_sw_comp = [round(i * employee_info[kCompCapSWIndex],2) for i in total_comp]
        self.total_employee_comp = total_comp
        self.cap_sw_comp = cap_sw_comp

    def Employee_Comp(self, employee_info, zero_expenses, inputs):

        self.comp_expenses = zero_expenses.copy()

        # sb list comprehension
        for i,item in enumerate(zero_expenses):
            
            if (i >= int(employee_info[kCompBeginIndex])-1) and (i <= int(employee_info[kCompEndIndex])):
                
                self.comp_expenses[i] = round(float(employee_info[kCompMonthlyIndex]),2)

        return self.comp_expenses

    def Bonus(self, employee_info, zero_expenses, inputs):
        print("Bonus not yet implemented")

    def CapSW(self, employee_info, zero_expenses, inputs, emply_num):

        return
        self.CapSWComp = zero_expenses.copy()
        self.CapSW_months_amort = {}
        
        amount = round(float(employee_info[kCompMonthlyIndex]) * float(employee_info[kCompCapSWIndex]),2)
        amort_months = inputs.amort_comp_term
        amort = round(amount/amort_months,2)
        proj_start = inputs.projections_start
        proj_duration = inputs.months_total
        comp_start = int(employee_info[kCompBeginIndex])
        comp_end = int(employee_info[kCompEndIndex])
        comp_name = employee_info[kCompNameIndex]

        if comp_start < proj_start:
            comp_start = proj_start        
        
        # sb list comprehension
        for i in range(comp_start , comp_end) :
            self.CapSWComp[i] = amount
            new_amort_list = zero_expenses.copy()
            self.CapSW_months_amort[i] = new_amort_list

        for key in self.CapSW_months_amort:
            i = key
            if i + amort_months > proj_duration:
                comp_end = proj_duration

            # sb list comprehension
            while (i >= key) and (i < comp_end):  # used to be "end"
                self.CapSW_months_amort[key][i] = amort
                i +=1

        self.CapSWAmort = zero_expenses.copy()

        # sb list comprehension
        for i in range(comp_start , proj_duration):
            for key in self.CapSW_months_amort:
                self.CapSWAmort[i] = self.CapSWAmort[i] + self.CapSW_months_amort[key][i]

        return self.CapSWComp, self.CapSWAmort        

    def Vacation(self, employee_info, zero_expenses, inputs):
        print("Vacation not yet implemented")

    def FICA(self, employee_info, zero_expenses, inputs):

        rate = float(inputs.FICA_rate)
        cap = float(inputs.FICA_cap)
        self.FICA_expenses = self.TaxCapCalc(rate, cap, zero_expenses, inputs)
        return self.FICA_expenses

    def Medicare(self, employee_info, zero_expenses, inputs):

        rate = float(inputs.Medicare_rate)
        self.Medicare_expenses = zero_expenses.copy()

        i = 0
        for amount in self.comp_expenses:
            self.Medicare_expenses[i] = round(amount*rate,2)
            i +=1
            
        return self.Medicare_expenses

    def FUTA(self, employee_info, zero_expenses, inputs):
        rate = float(inputs.FUTA_rate)
        cap = float(inputs.FUTA_cap)
        self.FUTA_expenses = self.TaxCapCalc(rate, cap, zero_expenses, inputs)
        return self.FUTA_expenses

    def SUI(self, employee_info, zero_expenses, inputs):
        rate = float(inputs.SUI_rate)
        cap = float(inputs.SUI_cap)
        self.SUI_expenses = self.TaxCapCalc(rate, cap, zero_expenses, inputs)
        return self.SUI_expenses

    def Health(self, employee_info, zero_expenses, inputs):     
        self.Healthcare_expenses = zero_expenses.copy()
        i = 0
        for i,item in enumerate(zero_expenses):
            if (i >= int(employee_info[kCompBeginIndex])-1) and (i <= int(employee_info[kCompEndIndex])):
                self.Healthcare_expenses[i] = float(employee_info[11])
            i +=1

        return self.Healthcare_expenses
        

    def WC(self, employee_info, zero_expenses, inputs):
        print("WC not yet implemented")

    def EmplSetup(self, employee_info, zero_expenses, inputs):
        print("EmplSetup not yet implemented")

    def TaxCapCalc(self, rate, cap, zero_expenses, inputs):

        a_month = relativedelta(months=1)
        pmtotal = 0
        cmtotal = 0
        dates = inputs.dates
        pmonth = (dates.start_date - a_month).month
        cmonth = dates.start_date.month
        month_date = dates.start_date

        self.taxes_out = zero_expenses.copy()

        i = 0
        for amount in self.comp_expenses:

            cmtotal += amount
            
            if (pmtotal < cap) and (cmtotal > cap):
                self.taxes_out[i] = round((cap - pmtotal)*rate,2)

            elif(pmtotal >= cap):
                self.taxes_out[i] = 0.0

            else:
                self.taxes_out[i] = round(amount*rate,2)

            if  cmonth == 12: 
                pmtotal = 0
                cmtotal = 0

            else:
                pmtotal = cmtotal

            i +=1

            pmonth = month_date.month
            month_date += a_month
            cmonth = month_date.month

        return self.taxes_out


            


        

