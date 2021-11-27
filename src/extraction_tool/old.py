#!/usr/bin/python3
file_obj = open("n101_PracExam1.ipynb", 'r')#n101_PracExam1
student = file_obj.readlines()
file_obj1 = open("solution.ipynb", 'r')
solution = file_obj1.readlines()
ignore = False
code_from_student = list()
student_cell = list()


for i in range(len(student)):
    student_cell.append(student[i])
    if "cell_type" in student[i]:
        if "code" not in student[i]:
            ignore = True
        else:
            ignore = False
    if ignore:
        continue
    if ignore==False:
        code_from_student.append(student[i])



each_answer_student = list()
answer_list = list()
for i in range(len(code_from_student)):
    if "source" in code_from_student[i]:
        
        if "[]" in code_from_student[i]:
            answer_list.append("")
            each_answer_student= []
        i+=1 #remove the "source" from list
        while "cell_type" not in code_from_student[i]:
            if i>=len(code_from_student)-1:
                break
            each_answer_student.append(code_from_student[i])
            i+=1
        if "cell_type" in code_from_student[i]:
            answer_list.append(each_answer_student)
            each_answer_student= []

for i in range(len(student)):
        print(student[i])
only_q1q4 = list()
only_q1q4.append(answer_list[0])
only_q1q4.append(answer_list[3])

for i in range(len(only_q1q4)):
    for j in range(len(only_q1q4[i])):
        only_q1q4[i][j] = only_q1q4[i][j][4:]#remove all the space for the first 4 spaces
        only_q1q4[i][j] = only_q1q4[i][j].replace(chr(34), "",1) #remove the " in the first
        if len(only_q1q4[i][j])>=2 and only_q1q4[i][j][-2] == chr(34):
            only_q1q4[i][j] = only_q1q4[i][j].replace(chr(34), "",-2) # need change if it's python2
        only_q1q4[i][j] = only_q1q4[i][j].replace(chr(92)+"n"+chr(34)+",", "")
        if only_q1q4[i][j] == ",":
            only_q1q4[i][j] = ""
        for k in range(len(only_q1q4[i][j])):
            if only_q1q4[i][j][k] == "#":
                only_q1q4[i][j] = only_q1q4[i][j][0:k] #remove comment
                break



txtFile=open("q1q4.py","w")
for i in range(len(only_q1q4)):
    for j in range(len(only_q1q4[i])):
        if len(only_q1q4[i][j])>0: # delete some space lines
            txtFile.write(only_q1q4[i][j])
            txtFile.write("\n")
txtFile.close()

#34 -> “	Double quotes (or speech marks)
#92	1011100	134	5C	\	Backslash

#用题号 抓题 要改 celltype前判定题号