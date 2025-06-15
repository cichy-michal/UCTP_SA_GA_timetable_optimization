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
            hard_penalty += 1000 * (count - 1)
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
            hard_penalty += 1000 * (count - 1)
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
            hard_penalty += 1000 * (count - 1)
            #h3_2 += 1
    #H4:
    for cid in schedule:
        for day, period, f, g in schedule[cid]:
            if (cid, day, period) in data["constraints"]:
                hard_penalty += 1000
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
    
def simulated_annealing(data, gauss, initial_temp=1000, cooling_rate=0.5, max_iterations=500):
    current_schedule, current_hard, current_soft, current_penalty = random_solution(data)
    best_schedule = deepcopy(current_schedule)
    best_hard, best_soft, best_penalty = current_hard, current_soft, current_penalty
    temp = initial_temp
    n1_count, n2_count, n3_count, n1_contribution, n2_contribution, n3_contribution = 0, 0, 0, 0, 0, 0
    n1_prob, n2_prob = 1/3, 2/3
    write_sa = []
    write_sa.append(['Iteracja', 'Temperatura', 'Hard penalty', 'Soft penalty', 'Total penalty', f"Temp: {initial_temp}, Cooling:{cooling_rate}"])
    write_sa.append([0, temp, current_hard, current_soft, current_penalty, n1_count, n2_count, n3_count])
    for i in range(max_iterations):
        if n1_contribution != 0 and n2_contribution != 0 and n3_contribution != 0:
            n1_prob = n1_contribution/(n1_contribution + n2_contribution + n3_contribution)
            n2_prob = n1_contribution + n2_contribution/(n1_contribution + n2_contribution + n3_contribution)
            n1_contribution, n2_contribution, n3_contribution = 0, 0, 0
        else:
            n1_prob, n2_prob = 1/3, 2/3
        cids = list(current_schedule.keys())
        random.shuffle(cids)
        for cid in cids:
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
                if roulette <= n1_prob:
                    neighbor_schedule_1 = dict(neighbor_schedule)
                    neighbor_schedule_1[cid][lecture - 1] = (new_day, new_period, room, lecture_num)
                    neighbor_hard, neighbor_soft, neighbor_penalty = penalty(neighbor_schedule_1, data)
                elif roulette <= n2_prob and roulette > n1_prob:
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
                    current_hard, current_soft, current_penalty = neighbor_hard, neighbor_soft, neighbor_penalty
                    if roulette <= n1_prob and -diffrence > 0:
                        n1_count += 1
                        n1_contribution += -diffrence
                        current_schedule = deepcopy(neighbor_schedule_1)
                    elif roulette <= n2_prob and roulette > n1_prob and -diffrence > 0:
                        n2_count += 1
                        n2_contribution += -diffrence
                        current_schedule = deepcopy(neighbor_schedule_2)
                    elif roulette > n2_prob and -diffrence > 0:
                        n3_count += 1
                        n3_contribution += -diffrence
                        current_schedule = deepcopy(neighbor_schedule_3)
                    if current_penalty < best_penalty:
                        best_schedule = deepcopy(current_schedule)
                        best_hard, best_soft, best_penalty = current_hard, current_soft, current_penalty
        write_sa.append([int(i+1), temp, current_hard, current_soft, current_penalty, n1_count, n2_count, n3_count])
        temp *= cooling_rate
    save_to_csv(os.path.join(current_dir, "wyniki", f"{os.path.splitext(instance)[0]}", "sa_process.csv"), write_sa, append=True)
    return best_schedule, best_hard, best_soft, best_penalty

class EvolutionAlgorithm:
    def __init__(self, pop_size=100, generations=250, mut_prob=0.01, cross_prob=0.1, Tour=5, elite_ratio=0.01):
        self.pop_size = pop_size
        self.generations = generations
        self.cross_prob = cross_prob
        self.mut_prob = mut_prob
        self.Tour = Tour
        self.elite_ratio = elite_ratio
        self.pop = []
        for i in range(pop_size):
            self.pop.append(random_solution(data))

    def evolve(self):
        write_GA = []
        write_GA.append([instance + ', Pop_size: ' + str(self.pop_size) + ', Gens: ' + str(self.generations) + ', Cross_prob: ' + str(self.cross_prob) 
                         + ', Mut_prob: ' + str(self.mut_prob) + ', Tour: ' + str(self.Tour)+ ', elite_ratio: ' + str(self.elite_ratio) + ', Mutacja: change/swap' + ', Krzyzowanie: OX'])
        write_GA.append(['Epoka EA', 'best', 'average', 'worst'])
        for i in range(self.generations):
            print(f"Generacja nr: {i+1}")
            new_pop = []
            for individual in self.selection_elitism():
                new_pop.append(individual)
            write_GA.append([int(i), best_solution(self.pop)[3], avg_solution(self.pop), worst_solution(self.pop)[3]])
            while len(new_pop) != self.pop_size:
                p1, p2 = self.selection_tournament(), self.selection_tournament()
                if random.random() < self.cross_prob:
                    individual = self.crossover_OX(p1, p2)
                else: individual = p1
                #if random.random() < self.mut_prob:
                individual = self.mutate(individual)
                new_pop.append(individual)
            self.pop = new_pop
        write_GA.append([int(self.generations), best_solution(self.pop)[3], avg_solution(self.pop), worst_solution(self.pop)[3]])
        save_to_csv(os.path.join(current_dir, "wyniki", f"{os.path.splitext(instance)[0]}", "ga_process.csv"), write_GA, append=True)

    def selection_elitism(self):
        sorted_pop = sorted(self.pop, key=lambda p: p[3])
        elite_pop = sorted_pop[:int(len(self.pop)*self.elite_ratio)]
        return elite_pop

    def selection_tournament(self):
        tournament = random.sample(self.pop, self.Tour)
        best_individual = min(tournament, key=lambda p: p[3])
        return best_individual

    def crossover_OX(self, p1, p2):
        keys = list(p1[0].keys())
        cut1, cut2 = sorted(random.sample(range(len(keys)), 2))
        p1_part = {}
        p2_part = {}
        o1 = {}
        for node in range(cut1, cut2):
            cid = keys[node]
            p1_part[cid] = p1[0][cid]
            o1[cid] = p1[0][cid]
        for cid in keys:
            if cid not in p1_part:
                p2_part[cid] = p2[0][cid]
        for cid in keys:
            if cid not in o1:
                o1[cid] = p2_part[cid]
        o1_hard, o1_soft, o1_penalty = penalty(o1, data)
        return o1, o1_hard, o1_soft, o1_penalty

    def mutate(self, solution):
        current_schedule = solution[0]
        current_hard, current_soft, current_penalty = solution[1], solution[2], solution[3]
        cids = list(current_schedule.keys())
        random.shuffle(cids)
        for cid in cids:
            for a, b, c, lecture in current_schedule[cid]:
                if random.random() < self.mut_prob:
                    #cid = random.choice(list(solution[0].keys()))
                    #lectures = solution[0][cid]
                    #lecture = random.randint(0, len(lectures)-1)
                    neighbor_schedule = deepcopy(current_schedule)
                    day, period, room, lecture_num = current_schedule[cid][lecture - 1]
                    rand_cid = random.choice(list(neighbor_schedule.keys()))
                    lectures = neighbor_schedule[rand_cid]
                    rand_lecture = random.randint(0, len(lectures)-1)
                    new_day = random.randint(0, data["days"]-1)
                    new_period = random.randint(0, data["periods_per_day"]-1)
                    new_room = random.choice(list(data["rooms"].keys()))
                    roulette = random.random()
                    if roulette <= 1/3:
                        neighbor_schedule_1 = dict(neighbor_schedule)
                        neighbor_schedule_1[cid][lecture - 1] = (new_day, new_period, room, lecture_num)
                    elif roulette <= 2/3 and roulette > 1/3:
                        neighbor_schedule_2 = dict(neighbor_schedule)
                        neighbor_schedule_2[cid][lecture - 1] = (day, period, new_room, lecture_num)
                    else:
                        neighbor_schedule_3 = dict(neighbor_schedule)
                        swap_1_day, swap_1_period, swap_1_room, swap_1_lecture = neighbor_schedule_3[cid][lecture - 1]
                        swap_2_day, swap_2_period, swap_2_room, swap_2_lecture = neighbor_schedule_3[rand_cid][rand_lecture]
                        neighbor_schedule_3[cid][lecture - 1] = (swap_2_day, swap_2_period, swap_2_room, swap_1_lecture)
                        neighbor_schedule_3[rand_cid][rand_lecture] = (swap_1_day, swap_1_period, swap_1_room, swap_2_lecture)
                    if roulette <= 1/3:
                        current_schedule = deepcopy(neighbor_schedule_1)
                    elif roulette <= 2/3 and roulette > 1/3:
                        current_schedule = deepcopy(neighbor_schedule_2)
                    else:
                        current_schedule = deepcopy(neighbor_schedule_3)
                    current_hard, current_soft, current_penalty = penalty(neighbor_schedule, data)
        return current_schedule, current_hard, current_soft, current_penalty

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
    instances = ['comp01.ctt.txt']
    write = []
    write_tuning = []
    write.append(['Instancja', 'Algorytm losowy', None, None, None, None, 'Simulated Annealing', None, None, None, None, None,
    'Algorytm Genetyczny', None, None, None, None, None])
    write.append([None, 'best', 'avg', 'worst', 'std', 'avg time [s]', 'best', 'avg', 'worst', 'std','hard_constraints',
                   'avg time [s]', 'best', 'avg', 'worst', 'std','hard_constraints', 'avg time [s]'])
    for instance in instances:
        sa_pop = []
        sa_gauss_pop = []
        random_pop = []
        ga_solutions = []
        time_random_pop = []
        time_sa_pop = []
        time_ga_pop = []
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
        for i in range(10):
            start_time_sa = time.time()
            print(f"Interacja nr: {i+1}")
            #cooling = 0
            #for j in range(19):
                #cooling += 0.05
            sa_pop.append(simulated_annealing(data, False))
            end_time_sa = time.time()
            time_sa_pop.append(end_time_sa - start_time_sa)
        #write_tuning.append(("Initial temp", "SA_best", f"Instancja {os.path.splitext(instance)[0]}"))
        #for sa in sa_pop:
        #    write_tuning.append((cooling, sa[3]))
        #save_to_csv(os.path.join(current_dir, "tuning.csv"), write_tuning)
        best_sa = best_solution(sa_pop)
        #print("GA")
        #for i in range(10):
            #start_time_ga = time.time()
            #cross_prob = 0
            #ga = EvolutionAlgorithm(cross_prob)
            #for j in range(10):
            #    cross_prob += 0.1
            #ga = EvolutionAlgorithm()
            #ga.evolve()
            #ga_solutions.append(best_solution(ga.pop))
            #end_time_ga = time.time()
            #time_ga_pop.append(end_time_ga - start_time_ga)
        #write_tuning.append(("Pop_size", "GA_best", f"Instancja {os.path.splitext(instance)[0]}"))
        #for ea in ga_solutions:
        #    write_tuning.append((ga.cross_prob, ea[3]))
        #save_to_csv(os.path.join(current_dir, "tuning.csv"), write_tuning)
        #best_ga = best_solution(ga_solutions)
        #print("Sa Gauss")
        #for i in range(10):
        #    sa_gauss_pop.append(simulated_annealing(data, True))
        #best_sa_gauss = best_solution(sa_gauss_pop)
        #html = generate_html_timetable(best_random[0], data)
        #save_html_timetable(os.path.join(current_dir, "wyniki", f"{os.path.splitext(instance)[0]}"), "random_timetable.html", html)
        #html = generate_html_timetable(best_sa[0], data)
        #save_html_timetable(os.path.join(current_dir,"wyniki", f"{os.path.splitext(instance)[0]}"), "sa_timetable.html", html)
        #html = generate_html_timetable(best_ga[0], data)
        #save_html_timetable(os.path.join(current_dir,"wyniki", f"{os.path.splitext(instance)[0]}"), "ga_timetable.html", html)
        write.append([os.path.splitext(instance)[0], best_random[3], avg_solution(random_pop), worst_solution(random_pop)[3], std_solution(random_pop), avg_time(time_random_pop),
                      best_sa[3], avg_solution(sa_pop), worst_solution(sa_pop)[3], std_solution(sa_pop), best_sa[1]/1000, avg_time(time_sa_pop)])
                      #best_ga[3], avg_solution(ga_solutions), worst_solution(ga_solutions)[3], std_solution(ga_solutions), best_ga[1]/1000, avg_time(time_ga_pop)])
    #std_solution(ga_solutions)
    save_to_csv(os.path.join(current_dir, "solution.csv"), write)
    end_time = time.time()
    print(f"Czas wykonania: {(end_time-start_time)//60} minut, {(end_time-start_time)%60} sekund")
    