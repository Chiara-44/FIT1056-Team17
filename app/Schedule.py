class ScheduleManager:
    """The main controller for all business logic and data handling."""
    def __init__(self, data_path="data/msms.json"):
        self.data_path = data_path
        self.clients = []


    def _load_data(self):
        """Loads data from the JSON file and populates the object lists."""
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                # Load students, teachers, and courses as before.
                self.students = self.build_students(data.get("students", []))
                self.teachers = self.build_teachers(data.get("teachers", []))
                self.courses = self.build_courses(data.get("courses", []))

                # Plain data - no object wrapping needed, so just pull it straight out.
                self.next_student_id = data.get("next_student_id", 1)
                self.next_teacher_id = data.get("next_teacher_id", 1)
                self.next_lesson_id = data.get("next_lesson_id", 1)

                # Correctly load the attendance log.
                # Use .get() with a default empty list to prevent errors if the key doesn't 
                # exist.
                self.attendance_log = data.get("attendance", [])
        except FileNotFoundError:
            print("Data file not found. Starting with a clean state.")
    
    def _save_data(self):
        """Converts object lists back to dictionaries and saves to JSON."""
        # Create a 'data_to_save' dictionary.
        data_to_save = {
            "students": [s.__dict__ for s in self.students],
            "teachers": [t.__dict__ for t in self.teachers],
            "courses": [c.__dict__ for c in self.courses],
            # Add the attendance_log to the dictionary to be saved.
            # Since it's already a list of dicts, no conversion is needed.
            "attendance": self.attendance_log,
            "next_student_id": self.next_student_id,
            "next_teacher_id": self.next_teacher_id,
            "next_lesson_id": self.next_lesson_id,
        }
        # Write 'data_to_save' to the JSON file.
        with open(self.data_path, 'w') as f:
            json.dump(data_to_save, f, indent=4)

    def build_students(self, student_dicts):
        """Converts a list of raw student dictionaries into StudentUser objects."""
        students = []
        for student_dict in student_dicts:
            id = student_dict["student_id"]
            name = student_dict["name"]
            enrolled_in = student_dict.get("enrolled_in", [])
            students.append(StudentUser(id, name, enrolled_in))
        return students

    def build_teachers(self, teacher_dicts):
        """Converts a list of raw teacher dictionaries into TeacherUser objects."""
        teachers = []
        for teacher_dict in teacher_dicts:
            id = teacher_dict["teacher_id"]
            name = teacher_dict["name"]
            speciality = teacher_dict["speciality"]
            teachers.append(TeacherUser(id, name, speciality))
        return teachers

    def build_courses(self, course_dicts):
        """Converts a list of raw course dictionaries into Course objects."""
        courses = []
        for course_dict in course_dicts:
            course_id = course_dict["course_id"]
            name = course_dict["name"]
            instrument = course_dict["instrument"]
            teacher_id = course_dict.get("teacher_id")
            enrolled_student_ids = course_dict.get("enrolled_student_ids", [])
            lessons = course_dict.get("lessons", [])
            courses.append(Course(course_id, name, instrument, teacher_id,
                                enrolled_student_ids, lessons))
        return courses
