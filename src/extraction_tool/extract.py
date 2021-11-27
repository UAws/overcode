# coding=utf-8
import argparse
import errno
import fnmatch
import re
import os

from os import path


# Add possible options to the command line interface

def argument_handler():
    parser = argparse.ArgumentParser()

    # the path to the original student's submission
    parser.add_argument('-d', '--base_dir', metavar='TARGET_DIR',
                        help='Path to a directory containing ipynb file')

    parser.add_argument('-q', '--question_number', nargs='+', help='<Required> Set flag', required=True)
    # Use like:
    # python arg.py -l 1234 2345 3456 4567

    parser.add_argument('-a', '--append_file_path', metavar='TARGET_DIR',
                        help='Path to a directory containing ipynb file')


    args = parser.parse_args()

    return args


# https://stackoverflow.com/questions/2186525/how-to-use-glob-to-find-files-recursively
def find_all_ipynb_path(path_from_args):
    matches = []
    for root, dirnames, filenames in os.walk(path_from_args):
        for filename in fnmatch.filter(filenames, '*.ipynb'):
            matches.append(os.path.join(root, filename))
    return matches


def open_and_format_code_from_file(individual_path_of_submission):
    file_obj = open(individual_path_of_submission, 'r')  # n101_PracExam1
    student = file_obj.readlines()
    # file_obj1 = open("solution.ipynb", 'r')
    # solution = file_obj1.readlines()
    ignore = False
    inner_code_from_student = list()
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
        if ignore == False:
            inner_code_from_student.append(student[i])

    return inner_code_from_student


def all_answers_of_one_student(code_from_student):
    each_answer_student = list()
    inner_answer_list = list()

    for i in range(len(code_from_student)):
        if "source" in code_from_student[i]:

            if "[]" in code_from_student[i]:
                inner_answer_list.append("")
                each_answer_student = []
            i += 1  # remove the "source" from list
            while "cell_type" not in code_from_student[i]:
                if i >= len(code_from_student) - 1:
                    break
                each_answer_student.append(code_from_student[i])
                i += 1
            if "cell_type" in code_from_student[i]:
                inner_answer_list.append(each_answer_student)
                each_answer_student = []

    return inner_answer_list


# for i in range(len(student)):
#     print(student[i])

def optional_questions_extractor(required_questions_number_list, answer_list):
    selected_questions = list()

    for q_number in required_questions_number_list:
        if len(answer_list) >= 1:
            # the index of the list should be the question number - 1
            one_question = answer_list[int(q_number) - 1]

            if len(one_question) == 0:
                continue
            # one_question.insert(0, ' " start question {number}\n" '.format(number=q_number))
            # one_question.append(' "# end question {number}\n" '.format(number=q_number))
            selected_questions.append(one_question)

    for i in range(len(selected_questions)):
        for j in range(len(selected_questions[i])):
            selected_questions[i][j] = selected_questions[i][j][4:]  # remove all the space for the first 4 spaces
            selected_questions[i][j] = selected_questions[i][j].replace(chr(34), "", 1)  # remove the " in the first
            if len(selected_questions[i][j]) >= 2 and selected_questions[i][j][-2] == chr(34):
                selected_questions[i][j] = selected_questions[i][j].replace(chr(34), "",
                                                                            -2)  # need change if it's python2
            selected_questions[i][j] = selected_questions[i][j].replace(chr(92) + "n" + chr(34) + ",", "")
            if selected_questions[i][j] == ",":
                selected_questions[i][j] = ""
            for k in range(len(selected_questions[i][j])):
                if selected_questions[i][j][k] == "#":
                    selected_questions[i][j] = selected_questions[i][j][0:k]  # remove comment
                    break

    return selected_questions


def produce_final_extraction(file_name, question_contexts, append_file_path):
    # https://stackoverflow.com/a/12517490/14207562
    if not os.path.exists(os.path.dirname(file_name)):
        try:
            os.makedirs(os.path.dirname(file_name))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

    if append_file_path:
        with open(append_file_path, mode='r') as in_file, \
                open(file_name, mode='w') as out_file:
            for line in in_file:
                out_file.write(line)

    txt_file = open(file_name, "a")
    for i in range(len(question_contexts)):
        for j in range(len(question_contexts[i])):
            if len(question_contexts[i][j]) > 0:  # delete some space lines
                txt_file.write("    ")
                txt_file.write(question_contexts[i][j])
                txt_file.write("\n")
    txt_file.close()


# 34 -> "	Double quotes (or speech marks)
# 92	1011100	134	5C	\	Backslash

# 用题号 抓题 要改 celltype前判定题号

def main():
    args = argument_handler()

    matched_target_file_path_list = find_all_ipynb_path(args.base_dir)

    for target_file in matched_target_file_path_list:
        code_from_student = open_and_format_code_from_file(target_file)

        answer_list = all_answers_of_one_student(code_from_student)

        selected_questions = optional_questions_extractor(args.question_number, answer_list)

        # https://stackoverflow.com/a/8384838/14207562
        # https://stackoverflow.com/a/4444952/14207562
        result_save_path = path.join(args.base_dir, 'solution', path.splitext(path.basename(target_file))[0] + '.py')

        produce_final_extraction(result_save_path, selected_questions, args.append_file_path)


if __name__ == "__main__":
    main()
