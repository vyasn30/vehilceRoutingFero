# import sqlalchemy
from sqlalchemy import Column, String, Integer, ForeignKey, create_engine, PickleType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# postgres db configration
db_username = os.getenv("db_username", "postgres")
db_pass = os.getenv("db_pass", "pass")
db_name = os.getenv("db_name", "celery_task_db")


# engine = create_engine("sqlite:///celery_task.db", echo=True)
engine = create_engine(f"postgresql://{db_username}:{db_pass}@localhost:5432/{db_name}")
db_Session = sessionmaker()
db_Session.configure(bind=engine)
Base = declarative_base()

# database table defination
class CeleryTask_model(Base):
    """
        CeleryTask model table
        input_data and out_data are dict which are stored.
        status represenets celery task's status.
        task_type represents type of optimization is happending (Single Trip, Multiple Driver and Multiple Driver with Time window)
    """

    __tablename__ = "Celery_Task"
    id = Column(String, primary_key=True)
    input_data = Column(PickleType)
    out_data = Column(PickleType)
    status = Column(String)
    status_msg = Column(String)
    task_type = Column(String)

    def __init__(self, id, status, status_msg, task_type, input_data):
        self.id = id
        self.status = status
        self.status_msg = status_msg
        self.task_type = task_type
        self.input_data = input_data


# generate tables if not exists
Base.metadata.create_all(engine)


class CeleryTask_Query:
    """
        wrapper to perform CRUD operation of Celery Task table
    """

    def insert(self, CeleryTask_model):
        """
        insertes celerytask_model object into table
        """
        tmp_session = db_Session()
        tmp_session.add(CeleryTask_model)
        tmp_session.commit()
        tmp_session.close()

    def update_task(
        self, task_id, status=None, status_msg=None, input_data=None, out_data=None
    ):
        """
            updated given column's values in celerytask table
        """
        tmp_session = db_Session()
        task = (
            tmp_session.query(CeleryTask_model)
            .filter(CeleryTask_model.id == task_id)
            .first()
        )
        if task:
            if status:
                task.status = status
            if status_msg:
                task.status_msg = status_msg
            if input_data:
                task.input_data = input_data
            if out_data:
                task.out_data = out_data
        tmp_session.commit()
        tmp_session.close()

    def get_task(self, task_id):
        """
            retrieve celery task's information based on celery task's id
        """
        tmp_session = db_Session()
        task = (
            tmp_session.query(CeleryTask_model)
            .filter(CeleryTask_model.id == task_id)
            .first()
        )
        tmp_session.close()
        return task
