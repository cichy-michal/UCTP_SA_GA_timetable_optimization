import random
import csv
import os
import time
import math
from copy import deepcopy

def load_ctt_file(filename):
    with open(filename, 'r') as file:
        lines = file.readlines()
    name = ""
    days = periods_per_day = 0
    courses = {}
    rooms = {}
    curricula = []
    constraints = []
    reading_courses = reading_rooms = reading_curricula = reading_constraints = False
    for line in lines:
        line = line.strip()
        if not line or line == "END.":
            continue
        if line.startswith("Name:"):
            name = line.split(":")[1].strip()
        elif line.startswith("Days:"):
            days = int(line.split(":")[1].strip())
        elif line.startswith("Periods_per_day:"):
            periods_per_day = int(line.split(":")[1].strip())
        elif line.startswith("COURSES:"):
            reading_courses = True
            reading_rooms = reading_curricula = reading_constraints = False
            continue
        elif line.startswith("ROOMS:"):
            reading_rooms = True
            reading_courses = reading_curricula = reading_constraints = False
            continue
        elif line.startswith("CURRICULA:"):
            reading_curricula = True
            reading_courses = reading_rooms = reading_constraints = False
            continue
        elif line.startswith("UNAVAILABILITY_CONSTRAINTS:"):
            reading_constraints = True
            reading_courses = reading_rooms = reading_curricula = False
            continue
        if reading_courses:
            parts = line.split()
            cid, teacher, n_lectures, min_days, students = parts
            courses[cid] = {
                "teacher": teacher,
                "lectures": int(n_lectures),
                "min_days": int(min_days),
                "students": int(students)
            }
        elif reading_rooms:
            rid, capacity = line.split()
            rooms[rid] = int(capacity)
        elif reading_curricula:
            parts = line.split()
            curricula.append({
                "id": parts[0],
                "courses": parts[2:]
            })
        elif reading_constraints:
            cid, day, period = line.split()
            constraints.append((cid, int(day), int(period)))
    return {
        "name": name,
        "days": days,
        "periods_per_day": periods_per_day,
        "courses": courses,
        "rooms": rooms,
        "curricula": curricula,
        "constraints": constraints
    }

def check_hard_constraints(data, schedule, cid, day, period, room):
    course = data["courses"][cid]
    # H2
    for scheduled_cid in schedule:
        for scheduled_day, scheduled_period, scheduled_room, i in schedule[scheduled_cid]:
            if scheduled_day == day and scheduled_period == period and scheduled_room == room:
                return False
    # H3
    for scheduled_cid in schedule:
        if data["courses"][scheduled_cid]["teacher"] == course["teacher"]:
            for scheduled_day, scheduled_period, i, j in schedule[scheduled_cid]:
                if scheduled_day == day and scheduled_period == period:
                    return False
    for curriculum in data["curricula"]:
        if cid in curriculum["courses"]:
            for other_cid in curriculum["courses"]:
                if other_cid in schedule:
                    for scheduled_day, scheduled_period, i, j in schedule[other_cid]:
                        if scheduled_day == day and scheduled_period == period:
                            return False
    # H4
    if (cid, day, period) in data["constraints"]:
        return False
    return True

def random_solution(data):
    schedule = {}
    available_periods = []
    for day in range(data["days"]):
        for period in range(data["periods_per_day"]):
            for room in data["rooms"]:
                available_periods.append((day, period, room))
    random.shuffle(available_periods)
    courses = list(data["courses"].items())
    random.shuffle(courses)
    for cid, course in courses:
        schedule[cid] = []
        lectures_scheduled = 0
        unscheduled_lectures = []
        while lectures_scheduled < course["lectures"]:
            scheduled = False
            for slot in available_periods:
                day, period, room = slot
                if check_hard_constraints(data, schedule, cid, day, period, room):
                    schedule[cid].append((day, period, room, lectures_scheduled + 1))
                    lectures_scheduled += 1
                    available_periods.remove(slot)
                    scheduled = True
                    break
            if not scheduled:
                unscheduled_lectures.append((cid, lectures_scheduled + 1))
                lectures_scheduled += 1
        for cid, lecture_num in unscheduled_lectures:
            if available_periods:
                slot = available_periods.pop(0)
                day, period, room = slot
                schedule[cid].append((day, period, room, lecture_num))
            else:
                print(f"Nie przypisano: cid = {cid}, lecture_num = {lecture_num}")
    hard_penalty, soft_penalty, total_penalty = penalty(schedule, data)
    return schedule, hard_penalty, soft_penalty, total_penalty

'''
def penalty(schedule, data):
    hard_penalty = 0
    #h2, h3_1, h3_2, h4 = 0, 0, 0, 0
    #H2
    h2_rooms_used = {}
    for cid in schedule:
        for day, period, room, a in schedule[cid]:
            slot = (day, period, room)
            if slot not in h2_rooms_used:
                h2_rooms_used[slot] = 0
            h2_rooms_used[slot] += 1
    for count in h2_rooms_used.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h2 += 1
    #H3
    teacher_schedule = {}
    for cid in schedule:
        teacher = data["courses"][cid]["teacher"]
        for day, period, b, c in schedule[cid]:
            slot = (day, period, teacher)
            if slot not in teacher_schedule:
                teacher_schedule[slot] = 0
            teacher_schedule[slot] += 1
    for count in teacher_schedule.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h3_1 += 1
    #H3
    curriculum_slots = {}
    for curriculum in data["curricula"]:
        for cid in curriculum["courses"]:
            for day, period, d, e in schedule[cid]:
                slot = (curriculum["id"], day, period)
                curriculum_slots[slot] = curriculum_slots.get(slot, 0) + 1
    for count in curriculum_slots.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h3_2 += 1
    #H4:
    for cid in schedule:
        for day, period, f, g in schedule[cid]:
            if (cid, day, period) in data["constraints"]:
                hard_penalty += 100
                #h4 += 1
    soft_penalty = 0
    # S1
    for cid in schedule:
        students = data["courses"][cid]["students"]
        for day, period, room, i in schedule[cid]:
            if students > data["rooms"][room]:
                penalty = students - data["rooms"][room]
                soft_penalty += 1 * penalty
    # S2
    s2_rooms_used = {}
    for cid in schedule:
        rooms = set()
        for day, period, room, h in schedule[cid]:
            rooms.add(room)
        s2_rooms_used[cid] = rooms
        if len(rooms) > 1:
            soft_penalty += len(rooms) - 1
    # S3
    days_used = {}
    for cid in schedule:
        days = set()
        for day, b, c, d in schedule[cid]:
            days.add(day)
        days_used[cid] = days
        if len(days) < data["courses"][cid]["min_days"]:
            soft_penalty += 5 * (data["courses"][cid]["min_days"] - len(days))
    # S4
    day_periods = {}
    for curriculum in data["curricula"]:
        curr_id = curriculum["id"]
        day_periods[curr_id] = {}
        for cid in curriculum["courses"]:
            for day, period, a, b in schedule[cid]:
                if day not in day_periods[curr_id]:
                    day_periods[curr_id][day] = set()
                day_periods[curr_id][day].add(period)
        for day in day_periods[curr_id]:
            periods = sorted(day_periods[curr_id][day])
            for i in range(len(periods)-1):
                if periods[i+1] != periods[i] + 1:
                    soft_penalty += 2
    #structure = {
    #"H2": h2_rooms_used,
    #"H3_1": teacher_schedule,
    #"H3_2": curriculum_slots,
    #"S2": s2_rooms_used,
    #"S3": days_used,
    #"S4": day_periods
    #}
    #print(f"H2: {h2}, H3_1: {h3_1}, H3_2: {h3_2}, H4: {h4}")
    return hard_penalty, soft_penalty, hard_penalty + soft_penalty

#def incremental_penalty(schedule, data, old_slot, new_slot, structure):
    old_cid, old_day, old_period, old_room, old_lecture = old_slot
    new_cid, new_day, new_period, new_room, new_lecture = new_slot
    hard_change = 0
    soft_change = 0
    course = data["courses"][old_cid]
    teacher = course["teacher"]
    students = course["students"]
    min_days = course["min_days"]
    #H2
    old_room_slot = (old_day, old_period, old_room)
    count_old = structure["H2"].get(old_room_slot, 0)
    if count_old > 1:
        hard_change -= 100
    new_room_slot = (new_day, new_period, new_room)
    count_new = structure["H2"].get(new_room_slot, 0)
    if count_new >= 1:
        hard_change += 100
    structure["H2"][old_room_slot] -= 1
    if structure["H2"][old_room_slot] == 0:
        del structure["H2"][old_room_slot]
    if new_room_slot in structure["H2"]:
        structure["H2"][new_room_slot] += 1
    else:
        structure["H2"][new_room_slot] = 1
    # H3
    old_teacher_slot = (old_day, old_period, teacher)
    count_teacher_old = structure["H3_1"].get(old_teacher_slot, 0)
    if count_teacher_old > 1:
        hard_change -= 100
    new_teacher_slot = (new_day, new_period, teacher)
    count_teacher_new = structure["H3_1"].get(new_teacher_slot, 0)
    if count_teacher_new >= 1:
        hard_change += 100
    structure["H3_1"][old_teacher_slot] -= 1
    if structure["H3_1"][old_teacher_slot] == 0:
        del structure["H3_1"][old_teacher_slot]
    if new_teacher_slot in structure["H3_1"]:
        structure["H3_1"][new_teacher_slot] += 1
    else:
        structure["H3_1"][new_teacher_slot] = 1
    #H3
    curricula = [curr for curr in data["curricula"] if old_cid in curr["courses"]]
    for curr in curricula:
        curr_id = curr["id"]
        old_curr_slot = (curr_id, old_day, old_period)
        curr_conflicts_old = structure["H3_2"].get(old_curr_slot, 0)
        if curr_conflicts_old > 1:
            hard_change -= 100
        curr_conflicts_new = 0
        for cid in curr["courses"]:
            for day, period, a, b in schedule[cid]:
                if (day, period) == (new_day, new_period):
                    curr_conflicts_new += 1
        if curr_conflicts_new >= 1:
            hard_change += 100
        structure["H3_2"][old_curr_slot] -= 1
        if structure["H3_2"][old_curr_slot] == 0:
            del structure["H3_2"][old_curr_slot]
        new_curr_slot = (curr["id"], new_day, new_period)
        if new_curr_slot in structure["H3_2"]:
            structure["H3_2"][new_curr_slot] += 1
        else:
            structure["H3_2"][new_curr_slot] = 1
    #H4
    if (old_cid, old_day, old_period) in data["constraints"]:
        hard_change -= 100
    if (new_cid, new_day, new_period) in data["constraints"]:
        hard_change += 100
    #S1
    if students > data["rooms"][old_room]:
        soft_change -= (students - data["rooms"][old_room])
    if students > data["rooms"][new_room]:
        soft_change += (students - data["rooms"][new_room])
    # S2
    original_rooms = structure["S2"].get(old_cid, set())
    new_rooms = original_rooms - {old_room} | {new_room}
    delta = len(new_rooms) - len(original_rooms)
    soft_change += delta * 1
    structure["S2"][old_cid].remove(old_room)
    if not structure["S2"][old_cid]:
        del structure["S2"][old_cid]
    if old_cid in structure["S2"]:
        structure["S2"][old_cid].add(new_room)
    else:
        structure["S2"][old_cid] = {new_room}
    # S3
    original_days = structure["S3"].get(old_cid, set())
    new_days = original_days - {old_day} | {new_day}
    min_days = data["courses"][old_cid]["min_days"]
    if len(new_days) < min_days and len(original_days) >= min_days:
        soft_change += 5 * (min_days - len(new_days))
    elif len(new_days) >= min_days and len(original_days) < min_days:
        soft_change -= 5 * (min_days - len(original_days))
    elif len(new_days) < min_days and len(original_days) < min_days:
        soft_change += 5 * ((min_days - len(new_days)) - (min_days - len(original_days)))
    structure["S3"][old_cid].remove(old_day)
    if not structure["S3"][old_cid]:
        del structure["S3"][old_cid]
    if old_cid in structure["S3"]:
        structure["S3"][old_cid].add(new_day)
    else:
        structure["S3"][old_cid] = {new_day}
    #S4
    for curr in data["curricula"]:
        curr_id = curr["id"]
        if curr_id in structure["S4"]:
            if old_day in structure["S4"][curr_id]:
                periods = structure["S4"][curr_id][old_day]
                if old_period-1 in periods or old_period+1 in periods:
                    soft_change -= 2
            if new_day in structure["S4"][curr_id]:
                periods = structure["S4"][curr_id][new_day]
                if new_period-1 in periods or new_period+1 in periods:
                    soft_change += 2
            if old_day in structure["S4"][curr["id"]]:
                if old_period in structure["S4"][curr["id"]][old_day]:
                    structure["S4"][curr["id"]][old_day].remove(old_period)
                    if not structure["S4"][curr["id"]][old_day]:
                        del structure["S4"][curr["id"]][old_day]
            if new_day in structure["S4"][curr["id"]]:
                structure["S4"][curr["id"]][new_day].add(new_period)
            else:
                structure["S4"][curr["id"]][new_day] = {new_period}
    return hard_change, soft_change, hard_change + soft_change, structure
'''

def penalty(schedule, data):
    hard_penalty = 0
    #h2, h3_1, h3_2, h4 = 0, 0, 0, 0
    #H2
    rooms_used = {}
    for cid in schedule:
        for day, period, room, a in schedule[cid]:
            slot = (day, period, room)
            if slot not in rooms_used:
                rooms_used[slot] = 0
            rooms_used[slot] += 1
    for count in rooms_used.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h2 += 1
    #H3
    teacher_schedule = {}
    for cid in schedule:
        teacher = data["courses"][cid]["teacher"]
        for day, period, b, c in schedule[cid]:
            slot = (day, period, teacher)
            if slot not in teacher_schedule:
                teacher_schedule[slot] = 0
            teacher_schedule[slot] += 1
    for count in teacher_schedule.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h3_1 += 1
    curriculum_slots = {}
    for curriculum in data["curricula"]:
        curriculum_id = curriculum["id"]
        courses = curriculum["courses"]
        for cid in courses:
            for day, period, d, e in schedule[cid]:
                slot = curriculum_id, day, period
                if slot not in curriculum_slots:
                    curriculum_slots[slot] = 0
                curriculum_slots[slot] += 1
    for count in curriculum_slots.values():
        if count > 1:
            hard_penalty += 100 * (count - 1)
            #h3_2 += 1
    #H4:
    for cid in schedule:
        for day, period, f, g in schedule[cid]:
            if (cid, day, period) in data["constraints"]:
                hard_penalty += 100
                #h4 += 1
    soft_penalty = 0
    # S1
    for cid in schedule:
        students = data["courses"][cid]["students"]
        for day, period, room, i in schedule[cid]:
            if students > data["rooms"][room]:
                penalty = students - data["rooms"][room]
                soft_penalty += 1 * penalty
    # S2
    for cid in schedule:
        rooms_used = []
        for day, period, room, i in schedule[cid]:
            if room not in rooms_used:
                rooms_used.append(room)
        if len(rooms_used) > 1:
            penalty = len(rooms_used) - 1
            soft_penalty += 1 * penalty
    # S3
    for cid in schedule:
        days_used = []
        for day, period, room, i in schedule[cid]:
            if day not in days_used:
                days_used.append(day)
        min_days = data["courses"][cid]["min_days"]
        if len(days_used) < min_days:
            penalty = min_days - len(days_used)
            soft_penalty += 5 * penalty
    # S4
    for curriculum in data["curricula"]:
        curriculum_lectures = []
        for cid in curriculum["courses"]:
            curriculum_lectures.extend(schedule[cid])
        day_periods = {}
        for day, period, room, j in curriculum_lectures:
            if day not in day_periods:
                day_periods[day] = []
            if period not in day_periods[day]:
                day_periods[day].append(period)
        for day in day_periods:
            periods = sorted(day_periods[day])
            for i in range(len(periods) - 1):
                if periods[i+1] != periods[i] + 1:
                    soft_penalty += 2
    total_penalty = hard_penalty + soft_penalty
    #print(f"H2: {h2}, H3_1: {h3_1}, H3_2: {h3_2}, H4: {h4}")
    return hard_penalty, soft_penalty, total_penalty


def save_to_csv(filename, data):
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerows(data)

def generate_html_timetable(schedule, data):
    days = data["days"]
    periods_per_day = data["periods_per_day"]
    courses = data["courses"]
    curricula = data["curricula"]
    colors = ['bg-sky', 'bg-green', 'bg-yellow', 'bg-purple', 'bg-pink', 
              'bg-lightred', 'bg-light-blue', 'bg-light-green', 'bg-light-yellow']
    course_colors = {}
    color_index = 0
    for cid in courses.keys():
        course_colors[cid] = colors[color_index % len(colors)]
        color_index += 1
    curriculum_timetables = {}
    for curriculum in curricula:
        curriculum_id = curriculum["id"]
        curriculum_courses = curriculum["courses"]
        timetable = {}
        for day in range(days):
            timetable[day] = {}
            for period in range(periods_per_day):
                timetable[day][period] = []
        for cid in curriculum_courses:
            if cid in schedule:
                for day, period, room, lecture_num in schedule[cid]:
                    event = {
                        'cid': cid,
                        'teacher': courses[cid]["teacher"],
                        'lecture_num': lecture_num,
                        'room': room,
                        'capacity': data["rooms"][room],
                        'color': course_colors[cid]
                    }
                    timetable[day][period].append(event)
        curriculum_timetables[curriculum_id] = timetable
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>University Course Timetable</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .bg-sky { background-color: #02c2c7 }
            .bg-green { background-color: #5bbd2a }
            .bg-yellow { background-color: #fbb901 }
            .bg-purple { background-color: #9d60ff }
            .bg-pink { background-color: #ff6b98 }
            .bg-lightred { background-color: #ff4757 }
            .bg-light-blue { background-color: #70a1ff }
            .bg-light-green { background-color: #7bed9f }
            .bg-light-yellow { background-color: #fffa65 }
            .timetable-img { margin-bottom: 20px }
            .padding-5px-tb { padding-top: 5px; padding-bottom: 5px }
            .padding-15px-lr { padding-left: 15px; padding-right: 15px }
            .border-radius-5 { border-radius: 5px }
            .margin-10px-bottom { margin-bottom: 10px }
            .margin-10px-top { margin-top: 10px }
            .text-white { color: #fff !important }
            .text-light-gray { color: #d6d6d6 }
            .font-size16 { font-size: 16px }
            .font-size14 { font-size: 14px }
            .font-size13 { font-size: 13px }
            .bg-light-gray { background-color: #f5f5f5 }
            .period-header { font-weight: bold; background-color: #e9ecef }
            .curriculum-section { margin-bottom: 40px; border-bottom: 2px solid #dee2e6; padding-bottom: 20px }
            .curriculum-title { color: #2c3e50; margin-top: 30px; margin-bottom: 20px }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="timetable-img text-center">
                <h1 class="mt-4 mb-4">University Course Timetable</h1>
            </div>
    """
    for curriculum_id, timetable in curriculum_timetables.items():
        html += f"""
            <div class="curriculum-section">
                <h2 class="curriculum-title">Curriculum: {curriculum_id}</h2>
                <div class="table-responsive">
                    <table class="table table-bordered text-center">
                        <thead>
                            <tr class="bg-light-gray">
                                <th class="text-uppercase">Period</th>
        """
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in range(days):
            if day < len(day_names):
                day_name = day_names[day]
            else:
                day_name = f"Day {day + 1}"
            html += f'<th class="text-uppercase">{day_name}</th>'
        html += """
                            </tr>
                        </thead>
                        <tbody>
        """
        for period in range(periods_per_day):
            html += f"""
                            <tr>
                                <td class="period-header">Period {period+1}</td>
            """
            for day in range(days):
                events = timetable[day][period]
                if events:
                    event_html = []
                    for event in events:
                        event_html.append(f"""
                                    <span class="{event['color']} padding-5px-tb padding-15px-lr border-radius-5 margin-10px-bottom text-white font-size16 xs-font-size13">
                                        {event['cid']} ({event['lecture_num']})
                                    </span>
                                    <div class="margin-10px-top font-size14">Teacher: {event['teacher']}</div>
                                    <div class="margin-10px-top font-size14">{event['room']} (Capacity: {event['capacity']})</div>
                        """)
                    html += '<td>'
                    for element in event_html:
                        html += element
                    html += '</td>'
                else:
                    html += '<td class="bg-light-gray"></td>'
            html += """
                            </tr>
            """
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        """
    html += """
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html

def save_html_timetable(directory, filename, html_content):
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

def save_to_csv(filename, data, append=True):
    if append:
        mode = 'a'
    else:
        mode = 'w'
    with open(filename, mode=mode, newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerows(data)
    
def simulated_annealing(data, gauss, initial_temp=1000, cooling_rate=0.30, max_iterations=250):
    current_schedule, current_hard, current_soft, current_penalty = random_solution(data)
    best_schedule = deepcopy(current_schedule)
    best_hard, best_soft, best_penalty = current_hard, current_soft, current_penalty
    temp = initial_temp
    write_sa = []
    write_sa.append(['Iteracja', 'Temperatura', 'Hard penalty', 'Soft penalty', 'Total penalty'])
    write_sa.append([0, temp, current_hard, current_soft, current_penalty])
    for i in range(max_iterations):
        print(f"Interacja nr: {i+1}")
        for cid in current_schedule.keys():
            for a, b, c, lecture in current_schedule[cid]:
                neighbor_schedule = deepcopy(current_schedule)
                day, period, room, lecture_num = current_schedule[cid][lecture - 1]
                rand_cid = random.choice(list(current_schedule.keys()))
                lectures = current_schedule[rand_cid]
                rand_lecture = random.randint(0, len(lectures)-1)
                if gauss:
                    new_day = int(random.gauss(day, 1))
                    new_period = int(random.gauss(period, 1))
                    new_day = max(0, min(new_day, data["days"] - 1))
                    new_period = max(0, min(new_period, data["periods_per_day"] - 1))
                else:
                    new_day = random.randint(0, data["days"]-1)
                    new_period = random.randint(0, data["periods_per_day"]-1)
                new_room = random.choice(list(data["rooms"].keys()))
                roulette = random.random()
                if roulette < (1/3):
                    neighbor_schedule_1 = dict(neighbor_schedule)
                    neighbor_schedule_1[cid][lecture - 1] = (new_day, new_period, room, lecture_num)
                    neighbor_hard, neighbor_soft, neighbor_penalty = penalty(neighbor_schedule_1, data)
                elif roulette < (2/3):
                    neighbor_schedule_2 = dict(neighbor_schedule)
                    neighbor_schedule_2[cid][lecture - 1] = (day, period, new_room, lecture_num)
                    neighbor_hard, neighbor_soft, neighbor_penalty = penalty(neighbor_schedule_2, data)
                else:
                    neighbor_schedule_3 = dict(neighbor_schedule)
                    swap_1_day, swap_1_period, swap_1_room, swap_1_lecture = neighbor_schedule_3[cid][lecture - 1]
                    swap_2_day, swap_2_period, swap_2_room, swap_2_lecture = neighbor_schedule_3[rand_cid][rand_lecture]
                    neighbor_schedule_3[cid][lecture - 1] = (swap_2_day, swap_2_period, swap_2_room, swap_1_lecture)
                    neighbor_schedule_3[rand_cid][rand_lecture] = (swap_1_day, swap_1_period, swap_1_room, swap_2_lecture)
                    neighbor_hard, neighbor_soft, neighbor_penalty = penalty(neighbor_schedule_3, data)
                diffrence = neighbor_penalty - current_penalty
                if diffrence < 0 or (temp > 0 and random.random() < math.exp(-diffrence / temp)):
                    current_schedule = deepcopy(neighbor_schedule)
                    current_hard, current_soft, current_penalty = neighbor_hard, neighbor_soft, neighbor_penalty
                    if current_penalty < best_penalty:
                        best_schedule = deepcopy(current_schedule)
                        best_hard, best_soft, best_penalty = current_hard, current_soft, current_penalty
        write_sa.append([int(i+1), temp, current_hard, current_soft, current_penalty])
        temp *= cooling_rate
    save_to_csv(os.path.join(current_dir, "wyniki", f"{os.path.splitext(instance)[0]}", "sa_process.csv"), write_sa, append=True)
    return best_schedule, best_hard, best_soft, best_penalty

'''
def create_timetable(schedule):
    timetable = {}
    for cid in schedule:
        for day, period, room, lecture_num in schedule[cid]:
            timetable[(day, period, room)] = (cid, lecture_num)
    return timetable

class EvolutionAlgorithm:
    def __init__(self, pop_size=1000, generations=250, cross_prob=0.9, mut_prob=0.4, Tour=2, elite_ratio=0.1):
        self.pop_size = pop_size
        self.generations = generations
        self.cross_prob = cross_prob
        self.mut_prob = mut_prob
        self.Tour = Tour
        self.elite_ratio = elite_ratio
        self.pop = []
        for i in range(pop_size):
            self.pop.append(random_solution())

def evolve(self):
        write_EA = []
        write_EA.append([instance + ', Pop_size: ' + str(ea.pop_size) + ', Gens: ' + str(ea.generations) + ', Cross_prob: ' + str(ea.cross_prob) + ', Mut_prob: ' + str(ea.mut_prob) + ', Tour: ' + str(ea.Tour)+ ', elite_ratio: ' + str(ea.elite_ratio) + ', Mutacja: inverse' + ', Krzyzowanie: OX'])
        write_EA.append(['Epoka EA', 'best', 'average', 'worst'])
        for i in range(self.generations):
            new_pop = []
            for individual in self.selection_elitism():
                new_pop.append(individual)
            write_EA.append([int(i), evaluate(best_solution(self.pop)), avg_solution(self.pop), evaluate(worst_solution(self.pop))])
            while len(new_pop) != self.pop_size:
                p1, p2 = self.selection_tournament(), self.selection_tournament()
                if random.random() < self.cross_prob:
                    individual = self.crossover_OX(p1, p2)
                else: individual = deepcopy(p1)
                if random.random() < self.mut_prob:
                    individual = self.mutate_inverse(individual)
                new_pop.append(individual)
            self.pop = new_pop
        write_EA.append([int(self.generations), evaluate(best_solution(self.pop)), avg_solution(self.pop), evaluate(worst_solution(self.pop))])
        #save_to_csv(os.path.join(current_dir, "projekt0_met_opt.csv"), write_EA)

def selection_elitism(self):
        sorted_pop = sorted(self.pop, key=lambda p: p[3])
        elite_pop = sorted_pop[:int(len(self.pop)*self.elite_ratio)]
        return elite_pop

def selection_tournament(self):
        tournament = random.sample(self.pop, self.Tour)
        best_individual = min(tournament, key=lambda p: p[3])
        return best_individual

def crossover_OX(self, p1, p2, load=0):
        p1 = cut_depot(p1, depot)
        p2 = cut_depot(p2, depot)
        cut1, cut2 = sorted(random.sample(range(len(p1)), 2))
        p1_part = []
        p2_part = []
        o1 = [None] * len(p1)
        for node in range(cut1, cut2):
            p1_part.append(p1[node])
            o1[node] = p1[node]
        for node in p2:
            if node not in p1_part:
                p2_part.append(node)
        p2_part_node = 0
        for node in range(len(o1)):
            if o1[node] is None:
                o1[node] = p2_part[p2_part_node]
                p2_part_node += 1
        individual = [depot]
        for node in o1:
            individual, load = back_to_depot(node, individual, load, depot)
        if individual[-1] != depot:
                individual.append(depot)
        return individual

def mutate_inverse(self, solution, load=0):
            timetable = create_timetable(solution[0])

            inverse = [None] * len(solution)
            cut1, cut2 = sorted(random.sample(range(len(solution)), 2))
            node_inverse = cut2

            for node_solution in range(cut1, cut2+1):
                inverse[node_inverse] = solution[node_solution]
                node_inverse -= 1
            for node in range(len(inverse)):
                if inverse[node] is None:
                    inverse[node] = solution[node]
            
            new_solution = [depot]
            for node in inverse:
                new_solution, load = back_to_depot(node, new_solution, load, depot)
            if new_solution[-1] != depot:
                new_solution.append(depot)
            return new_solution
'''

def best_solution(pop):
    best = min(pop, key=lambda p: p[3])
    return best

def worst_solution(pop):
    worst = max(pop, key=lambda p: p[3])
    return worst
    
def avg_solution(pop):
    avg = sum(p[3] for p in pop) / len(pop)
    return avg

def avg_time(pop):
    avg = sum(p for p in pop) / len(pop)
    return avg

def std_solution(pop):
    avg = avg_solution(pop)
    std = (sum((p[3] - avg)**2 for p in pop)/ (len(pop) - 1))**0.5
    return std

if __name__ == "__main__":
    start_time = time.time()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    #instances = ['toy.ctt.txt','comp01.ctt.txt','comp02.ctt.txt','comp03.ctt.txt','comp04.ctt.txt','comp05.ctt.txt','comp06.ctt.txt','comp07.ctt.txt','comp08.ctt.txt','comp09.ctt.txt','comp10.ctt.txt',
    #           'comp11.ctt.txt','comp12.ctt.txt','comp13.ctt.txt','comp14.ctt.txt','comp15.ctt.txt','comp16.ctt.txt','comp17.ctt.txt','comp18.ctt.txt','comp19.ctt.txt','comp20.ctt.txt','comp21.ctt.txt']
    instances = ['toy.ctt.txt', 'comp01.ctt.txt', 'comp20.ctt.txt']
    write = []
    write.append(['Instancja', 'Algorytm losowy', None, None, None, None, 'Simulated Annealing', None, None, None, None])
    #'Algorytm Genetyczny', None, None, None])
    write.append([None, 'best', 'avg', 'worst', 'std', 'avg time [s]', 'best', 'avg', 'worst', 'std', 'avg time [s]'])
    for instance in instances:
        sa_pop = []
        sa_gauss_pop = []
        random_pop = []
        #ga_solutions = []
        time_random_pop = []
        time_sa_pop = []
        #time_ga_pop = []
        print(f"Instancja {os.path.splitext(instance)[0]}")
        data = load_ctt_file(os.path.join(current_dir, "instancje", instance))
        print("Random")
        for i in range(2):
            start_time_random = time.time()
            random_pop.append(random_solution(data))
            end_time_random = time.time()
            time_random_pop.append(end_time_random - start_time_random)
        best_random = best_solution(random_pop)
        print("SA")
        for i in range(2):
            start_time_sa = time.time()
            sa_pop.append(simulated_annealing(data, False))
            end_time_sa = time.time()
            time_sa_pop.append(end_time_sa - start_time_sa)
        best_sa = best_solution(sa_pop)
        #print("GA")
        #for i in range(2):
            #start_time_ga = time.time()
            #ga = EvolutionAlgorithm()
            #ga.evolve()
            #ga_solutions.append(best_solution(ga.pop))
            #end_time_ga = time.time()
            #time_ga_pop.append(end_time_ga - start_time_ga)
        #print("Sa Gauss")
        #for i in range(10):
        #    sa_gauss_pop.append(simulated_annealing(data, True))
        #best_sa_gauss = best_solution(sa_gauss_pop)
        #html = generate_html_timetable(best_random[0], data)
        #save_html_timetable(os.path.join(current_dir, "wyniki", f"{os.path.splitext(instance)[0]}"), "random_timetable.html", html)
        #html = generate_html_timetable(best_sa[0], data)
        #save_html_timetable(os.path.join(current_dir,"wyniki", f"{os.path.splitext(instance)[0]}"), "sa_timetable.html", html)
        write.append([os.path.splitext(instance)[0], best_random[3], avg_solution(random_pop), worst_solution(random_pop)[3], std_solution(random_pop), avg_time(time_random_pop),
                      best_sa[3], avg_solution(sa_pop), worst_solution(sa_pop)[3], std_solution(sa_pop), avg_time(time_sa_pop)])
    save_to_csv(os.path.join(current_dir, "solution.csv"), write)
    end_time = time.time()
    print(f"Czas wykonania: {(end_time-start_time)//60} minut, {(end_time-start_time)%60} sekund")
    