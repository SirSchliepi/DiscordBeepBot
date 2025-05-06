import random
import time
import json
from jsonschema import validate
from Levenshtein import distance, ratio

quiz_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "multiple": {"type": "boolean"},
            "categories": {"type": "array", "items": {"type": "string"}},
            "sourcecode": {"type": "string"},
            "image": {"type": "string"},
            "timeout": {"type": "integer"},
            "uuid": {"type": "string"},
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "correct": {"type": "boolean"},
                    },
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["question", "multiple", "categories", "timeout", "answers"],
        "additionalProperties": False,
    },
}


def get_uuid():
    randint = random.getrandbits(64)
    randstr = f"{randint:016x}"
    return randstr


def current_milli_time():
    return round(time.time() * 1000)


GLOBAL_MAX_TIMEOUT = 180
GLOBAL_MAX_QUESTION_LENGTH = 600
GLOBAL_DEFAULT_TIMEOUT = 20


class QuizException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class Answer:
    def __init__(self, answer: str, correct=False):
        if len(answer) > 50:
            raise QuizException("Answer exceeded max (>50) :" + answer)
        self.answer = answer
        self.correct = correct
        self.commited = False
        self.uuid = get_uuid()

    def is_correct(self):
        return self.correct

    def set_correct(self):
        self.correct = True

    def get_json(self):
        e = dict()
        e["answer"] = self.answer
        if self.correct:
            e["correct"] = True
        return e

    def __str__(self):
        return self.answer


class Question:
    def __init__(
        self,
        question: str,
        timeout=0,
        multiple=False,
        categories=[],
        sourcecode=None,
        image=None,
    ):
        self.answers = []
        self.image = None
        self.multiple = multiple
        self.question = question
        self.categories = categories
        self.sourcecode = sourcecode
        self.image = image
        self.uuid = get_uuid()
        self.set_timeout(timeout)

    def get_json(self):
        e = dict()
        e["question"] = self.question
        e["multiple"] = self.multiple
        e["categories"] = self.categories
        e["timeout"] = self.timeout
        if self.sourcecode:
            e["sourcecode"] = self.sourcecode
        if self.image:
            e["image"] = self.image
        
        e["uuid"] = self.uuid
        
        e["answers"] = []
        for a in self.answers:
            e["answers"].append(a.get_json())
        return e

    def add_answer(self, answer: Answer):
        self.answers.append(answer)

    def get_correct_list(self):
        return [a for a in self.answers if a.is_correct()]

    def get_answers(self):
        return self.answers

    def is_answer(self, answer):
        return answer in self.answers

    def is_multiple(self):
        return self.multiple

    def has_sourcecode(self):
        return self.sourcecode is not None

    def has_image(self):
        return self.image is not None

    def commit(self):
        correctAnz = 0
        for a in self.answers:
            if a.is_correct():
                correctAnz += 1

        if correctAnz == 0:
            raise QuizException("No correct answer added")
        if len(self.answers) < 2:
            raise QuizException("At least 2 answers necessary")
        if len(self.question) > GLOBAL_MAX_QUESTION_LENGTH:
            raise QuizException("Question length exceeded max")

        if not self.uuid or self.uuid == "":
            self.uuid = get_uuid()
        
        if self.sourcecode:
            self.sourcecode=str(self.sourcecode).replace('```','')
            if not self.sourcecode or self.sourcecode == "None":
                self.sourcecode=""
                
        self.timeout = max(0,self.timeout)
        self.timeout = min(GLOBAL_MAX_TIMEOUT,self.timeout)

        self.commited = True

    def set_timeout(self, timeout):
        if not timeout or timeout > GLOBAL_MAX_TIMEOUT or timeout <= 0:
            timeout = GLOBAL_DEFAULT_TIMEOUT
        self.timeout = timeout

    def add_category(self, c):
        if c not in self.categories:
            self.categories.append(c)

    def is_category(self, c):
        return len(set(c) & set(self.categories))>0

    def get_categories(self):
        return self.categories[:]

    def __str__(self):
        res = ""
        res += self.question + "\n"
        for i in range(1, len(self.answers) + 1):
            res += str(i) + ": " + str(self.answers[i - 1]) + "\n"
        res += "Correct: " + str([str(x) for x in self.get_correct_list()]) + "\n"
        res += "UUID: " + self.uuid
        return res

    def compare(self, q): 
        qstr1 = self.question+ str(a for a in self.answers)
        qstr2 = q.question+ str(a for a in q.answers)
        return ratio(qstr1,qstr2)

class Pool:
    def __init__(self):
        self.questions = list()
        self.count = 0
        self.catlist = None

    def get_json(self):
        e = []
        for n, q in self.questions:
            e.append(q.get_json())
        return json.dumps(e)

    def add_question(self, q: Question):
        self.questions.append((self.count, q))
        self.count = self.count + 1
        self.gen_catlist()

    def get_categories(self):
        if not self.catlist:
            self.gen_catlist()
        return self.catlist
        
    def gen_catlist(self):
        catlist=[]
        for n, q in self.questions:
            catlist.extend(q.get_categories())
        self.catlist= list(set(catlist))  

    def count_category_questions(self):
        res = {}
        for n, q in self.questions:
            for c in q.get_categories():
                res[c] = res.get(c,0)+1
        return res

    def get_questions(self, category=None, shuffle=True):
        qlist = []
        for nr, q in self.questions:
            if category and not q.is_category(category):
                continue
            qlist.append(q)

        if shuffle:
            random.shuffle(qlist)
            
        return qlist

    def get_question_by_uuid(self, uuid:str):
        if not uuid:
            return None
        
        for nr, q in self.questions:
            if (q.uuid == uuid):
                return q
        return None

    def remove_question(self, qe:Question):
        torem = None
        for x in self.questions:
            nr, q = x
            if q==qe:
                torem = x
        if torem:
            self.questions.remove(torem)
            self.count-=1
        
        
    def add_or_update(self, q:Question): 
        res = 'add'
        added = self.get_question_by_uuid(q.uuid)
        if added:
            self.remove_question(added)
            res = 'edit'
        self.add_question(q)
        return res
    
    def check_equality(self, q:Question):  
        found = []
        for nr,quest in self.questions:
            if quest.uuid == q.uuid:
                continue
            if q.compare(quest) > 0.93:
                found.append(quest)
        return found

    @classmethod
    def parse_json(cls, data):
        try:
            d = json.loads(data)
            validate(instance=d, schema=quiz_schema)
        except:
            
            return None

        mp: Pool = Pool()
        try:
            for qe in d:
                my_q = Question(
                    qe["question"], qe["timeout"], qe["multiple"], qe["categories"]
                )
                
                if "sourcecode" in qe:
                    my_q.sourcecode= qe["sourcecode"]

                if "uuid" in qe:
                    my_q.uuid= qe["uuid"]
        
                if "image" in qe:
                    my_q.image= qe["image"]
                
                for qa in qe["answers"]:
                    my_a = Answer(qa["answer"])
                    if "correct" in qa and qa["correct"] == True:
                        my_a.set_correct()
                    my_q.add_answer(my_a)
                mp.add_question(my_q)
                
                my_q.commit()
                
            mp.gen_catlist()
            return mp
        except Exception as error:
            raise QuizException("JSON not correctly formatted " + str(error))

        
class SessionGuess:
    def __init__(self, user, answer: Answer):
        self.user = user
        self.answer = answer
        self.time = current_milli_time()


class QuizSessionQuestion:
    def __init__(self, question: SessionGuess, number=0, total=0):
        self.question: Question = question
        self.guesses = dict()
        self.time = current_milli_time()
        self.number = number
        self.total =  total
        self.open = True


    def add_answer(self, answer: SessionGuess):
        if not self.open:
            return
        
        if not (self.question):
            return False
        if not self.question.is_answer(answer.answer):
            return False

        user = answer.user
        useranswer = answer.answer

        cur = self.guesses.get(user, dict())
        if self.question.is_multiple():
            cur["answer"] = cur.get("answer", list())
            if useranswer in cur["answer"]:
                cur["answer"].remove(useranswer)
            else:
                cur["answer"].append(useranswer)
        else:
            cur["answer"] = [useranswer]

        cur["time"] = answer.time
        self.guesses[user] = cur

        return True

    def anz_guesses(self):
        return len(self.guesses)
    
    def anz_correct_guesses(self):
        anz=0
        c_list = self.question.get_correct_list()
        for user, answer in self.guesses.items():
            if set(answer["answer"]) == set(c_list):
                anz+=1
        return anz
                
    def close(self):
        self.open=False
    
    def is_open(self):
        return self.open
        
    def is_first_answer(self, user):
        return not user in self.guesses

    def get_guesses_by_user(self, user):
        if user not in self.guesses:
            return []
        else:
            return self.guesses[user].get("answer", [])

    def get_timeout(self):
        return self.question.timeout

    def get_answers(self):
        return self.question.get_answers()

    def get_rank(self):
        c_list = self.question.get_correct_list()

        u_list = dict()
        for user, answer in self.guesses.items():
            if set(answer["answer"]) == set(c_list):
                u_list[user] = answer["time"]

        return dict(sorted(u_list.items(), key=lambda item: item[1]))


class QuizSession:
    def __init__(self, questions, show_correct=False):
        self.questions = questions
        self.uuid = get_uuid()
        self.is_running = False  # whole quiz
        self.cur_session_question = None
        self.is_open = False  # current
        self.show_correct = show_correct
        self.user = None
        self.session_point_list = dict()
        self.pause = False


    def start(self):
        if len(self.questions) == 0:
            raise QuizException("Empty Question Pool")

        if self.is_running:
            raise QuizException("Quiz is already running")

        self.question_pointer = 0

        self.is_running = True


    def stop(self):
        if not self.is_running:
            raise QuizException("Session is not running")

        self.is_running = False

    def is_next_question(self):
        if not self.is_running:
            return False
        return self.question_pointer < len(self.questions)

    def get_current_question(self):
        if not self.is_running:
            return None
        return self.cur_session_question

    def start_round(self):
        if self.is_open:
            self.end_round()
            
        anz = len(self.questions)
        q = self.questions[self.question_pointer]
        self.question_pointer += 1
        self.cur_session_question = QuizSessionQuestion(q, number=self.question_pointer, total=anz)
        self.is_open = True
        return q

    def __set_points(self,namen):
        basis = (4, 3, 2)                  
        return [basis[i] if i < len(basis) else 1 for i in range(len(namen))] 
    
    def prepare_rank(self):
        if not self.is_running or not self.cur_session_question:
            return
        
        qs = self.cur_session_question
        rank = qs.get_rank()
        nlist = rank.keys()
        points = self.__set_points(nlist)
        for u,p in zip(nlist,points):
            self.session_point_list[u] = self.session_point_list.get(u,0)+p
    
    def get_final_rank_list(self):
        res = {}
        for k,v in self.session_point_list.items():
            res[k.name]=int(v)
        return res           
            
    def end_round(self):
        if not self.is_running or not self.cur_session_question:
            return
        
        self.is_open = False
    
        return

    def get_current_point(self,user):
        if user not in self.session_point_list: 
            return 0
        else:
            return self.session_point_list[user]
        

    def add_guess(self, user, guess: Answer):
        if not self.is_open:
            return False

        if not self.is_running or not self.cur_session_question:
            return False

        g = SessionGuess(user, guess)
        if self.cur_session_question.add_answer(g):
            return True

        return False

    def get_poolsize(self):
        return len(self.questions)

    def finish(self):
        self.is_running = False

