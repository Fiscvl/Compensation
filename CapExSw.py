from datetime import *
from dateutil.relativedelta import *

import pandas as pd
from Constants import *
from operator import add

class  CCapExSW():

    def __init__(self, inputs, journal_entry, formats, employee_instance, contractor_instance):


        self.journal_entry = journal_entry
        self.month_transactions = {}
        self.account_pairs = {}
        close_TB = []
        close_TB_index = []
        self.journal_entry = journal_entry

        start = inputs.projections_start
        end = inputs.months_total
        
        excel_book = (inputs.full_path_input  + kTB_file)
        close_month_TB = inputs.projections_date.strftime("%Y-%m") 

        #get the last closed month TB to see if any CapExSW balances need to be amortized

        excel_book = (inputs.full_path_input + kcapSWAccts_file)
        self.capSWAccts_df = pd.read_excel(excel_book, kCapExSW)

        try:
            df = self.capSWAccts_df.copy()
            close_TB = df.values.tolist()

            if len(close_TB) > 0:
                for row in close_TB:
                   close_TB_index.append(row[kTBAcIndex])
                   
        except:
            print("Couldn't find or open the TB's Excel File. Close TB process halted", excel_book)

        try:
            excel = (inputs.full_path_input + kCapExSW)
            self.cap_ex_df = pd.read_excel(excel, kCapExSW)

        except:
            print("Coundn't find CapEx File")

        for i, row in self.capSWAccts_df.iterrows():
            cap_ex_sw_transactions = inputs.zero_row.copy()
            asset_ac = row[kCapExDebitIndex]
            contra_ac = row[kCapExAccumulatedIndex]
            continue_row = True
            sub_type = row[kCapExSubTypeIndex]

            if sub_type == kCapExCapType:

                try:
                    TB_index = close_TB_index.index(asset_ac)
                    asset = float(close_TB[TB_index][kDRIndex])
                except:
                    continue_row = False
                    print("Didn't find asset:", asset_ac)
                
                #print("Contra account: ", contra_ac)
                try:
                    TB_index_contra = close_TB_index.index(contra_ac)
                    contra = float(close_TB[TB_index_contra][kCRIndex])
                except:
                    contra = 0
                    print("Didn't find contra: ", contra_ac)

                if continue_row:
                    monthly = round((asset-contra)/row[kCapExInitialIndex],2)
                    #needs to be replaced with a list comprehension to fill the
                    month_start = inputs.months_actuals
                    for month in range(inputs.months_projections):
                        cap_ex_sw_transactions[month + month_start] = monthly 
                    
                    self.month_transactions[row[kCapExDebit]] = cap_ex_sw_transactions
                
                # send the entire row so we can choose which acs to use
                #try finding the asset account
                #if found and not zero then look for contra account, if not found the assign zero value
                #divide net amuont by term
                #fill the either the end of the term or the end of the projections, whichever comes first into the transaction vector

                # Here's the employees and contractors section for projected comp

        self.employee_capSW = employee_instance.capSW_dict[kCapSWTotals]
        self.contractor_capSW = contractor_instance.capSW_dict[kCapSWTotals]
        total_SW_comp = list(map(add, self.employee_capSW, self.contractor_capSW))

        amort = inputs.zero_row.copy()
        amort_term = inputs.amort_comp_term
        
        for i in range(start,end):
            monthly_amort = round(total_SW_comp[i]/amort_term,2)
            if end > i + amort_term:
                end_j = i + amort_term
            else: 
                end_j = end
            for j in range(i,end_j):
                #take the new month, divide by amort term and spread that over the months following that month until you reach the amort term or the end
                amort[j] = round(monthly_amort + amort[j],2)

        self.amort_expense_CapSW = amort

        # iterate thru capex ac list
        #   - if asset balance has a negative balance then error
        #   - if asset has a zero balance make sure it's contra account is zero, if not error
        #   - if asset has a positive balance, subtract the contra amount then amortize the net balance
        #        - by diving the net balance by the average term for that account and filling in the month vector from current month
        #        - to either the end of the term or the end of the projections, whichever comes first

        # Need to read
        #           - the accounts list for CapSW
        #           - the closing TB
        # Need to get the number of net CapSW accounts - zero vectors
        # Need to create a dic for each of the above vectors with asset ac as the key
        

        # Here is where I am; need to read all balances - asset and contra, determine net unamortized balance and then
        # amortize them over the standard estimated reaming life (an input)

        #print(f"Here's the self.month_transactions {self.month_transactions}")
        #print(f"Here's the self.account_pairs {self.account_pairs}")
            
        #except:
            #print("Can't open the CapExSW Excel file")

        #print("Got here in CapEx Class!")

        #self.comp_capsw = self.get_cap_sw_arrays(inputs, formats, compensation_instance)
        #self.constractors_capsw = self.get_cap_sw_arrays(inputs, formats, contractor_instance)

    def CCapExSWAddMonthsTransactions(self, month, current_TB, inputs):


        #Each projection month, take the "self.month_transactions" Dictionary
        #Loop thru each expense.  If the Expense has a 'Accumulated' account with an entry in the Dictionary
        #Take that entry's monthly expense vector, Debit a/c, Credit account, and month's amount (if non-zero)
        #And make the entry to the related monthly trial balance

        #print("Month number: ", month+1)

        #disable the module
        #return

        capSW_df = self.capSWAccts_df.loc[self.capSWAccts_df[kcapSWType] == kcapSWTypeSW]

        # not sure we need this anymore

        # This is for amortizing the initial balances 
        for i, row in self.capSWAccts_df.iterrows():

            sub_type = row[kCapExSubTypeIndex]
              
            if row[kCapExSubTypeIndex] == kCapSWExpType:

                DR = row[kCapExDebitIndex]
                CR = row[kCapExCreditIndex]
                accumulated = row[kCapExAccumulatedIndex]

                if accumulated in self.month_transactions:
                    amount = self.month_transactions[accumulated][month]
                    if amount != 0:
                        current_TB = self.journal_entry.performJE(month, current_TB, DR, CR, amount)

                else:
                    print("Capitalized item has a zero balance, no amortization required: ",accumulated)


        # Need to add the new balances each, both employees and contractors (2 JE's)
        # And record the current months amortization (one JE as the employees and contractors are combined when amortizing

        capSW_df = self.capSWAccts_df.loc[self.capSWAccts_df[kcapSWType] == kcapSWTypeSW]
        capSW_list = capSW_df.values.tolist()

        for row in capSW_list:
            if row[kcapSWCompTypeIndex] == kcapSWCompTypeEmpl:
                amount = round(self.employee_capSW[month],2)
                DR_acct = row[kcapSWCompDebitIndex]
                CR_acct = row[kcapSWCompCreditIndex]
                self.journal_entry.performJE(month, current_TB, DR_acct, CR_acct, amount)

            elif row[kcapSWCompTypeIndex] == kcapSWCompTypeCont:
                amount = round(self.contractor_capSW[month],2)
                DR_acct = row[kcapSWCompDebitIndex]
                CR_acct = row[kcapSWCompCreditIndex]
                self.journal_entry.performJE(month, current_TB, DR_acct, CR_acct, amount)

            elif row[kcapSWSubTypeIndex] == kcapSWSubTypeExp:
                amount = round(self.amort_expense_CapSW[month],2)
                DR_acct = row[kcapSWCompDebitIndex]
                CR_acct = row[kcapSWCompCreditIndex]

                self.journal_entry.performJE(month, current_TB, DR_acct, CR_acct, amount)

            else:
                print("Error in SW Accounts table, type unknown")

        return current_TB