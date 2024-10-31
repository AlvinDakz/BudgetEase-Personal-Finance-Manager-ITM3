from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime, timedelta


SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True)
    amount = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    category = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="transactions")

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    amount = Column(Float)
    category = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="budgets")

Base.metadata.create_all(bind=engine)


class UserCreate(BaseModel):
    name: str
    email: str

class TransactionCreate(BaseModel):
    description: str
    amount: float
    category: str
    date: Optional[datetime] = None

class BudgetCreate(BaseModel):
    name: str
    amount: float
    category: str
    start_date: datetime
    end_date: datetime


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="BudgetEase: Personal Finance Manager",
    description="Manage personal finances, track transactions and budgets.",
    version="2.0.0"
)


@app.post("/users/", response_model=UserCreate)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/{user_id}", response_model=UserCreate)
def get_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.put("/users/{user_id}", response_model=UserCreate)
def update_user(user_id: int, user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    for key, value in user.dict(exclude_unset=True).items():
        setattr(db_user, key, value)
    db.commit()
    return db_user


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted"}


@app.get("/users/email/{email}", response_model=List[UserCreate])
def filter_users_by_email(email: str, db: Session = Depends(get_db)):
    return db.query(User).filter(User.email == email).all()


@app.get("/transactions/date/", response_model=List[TransactionCreate])
def filter_transactions_by_date(start_date: datetime, end_date: datetime, db: Session = Depends(get_db)):
    return db.query(Transaction).filter(Transaction.date >= start_date, Transaction.date <= end_date).all()


@app.get("/transactions/category/{category}", response_model=List[TransactionCreate])
def filter_transactions_by_category(category: str, db: Session = Depends(get_db)):
    return db.query(Transaction).filter(Transaction.category == category).all()


@app.get("/transactions/user/{user_id}", response_model=List[TransactionCreate])
def get_transactions_for_user(user_id: int, db: Session = Depends(get_db)):
    return db.query(Transaction).filter(Transaction.user_id == user_id).all()


@app.get("/transactions/total_spent/{user_id}")
def get_total_spent(user_id: int, db: Session = Depends(get_db)):
    total_spent = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == user_id).scalar()
    return {"total_spent": total_spent}


@app.get("/transactions/count/")
def get_total_transactions_count(db: Session = Depends(get_db)):
    return {"total_transactions": db.query(Transaction).count()}


@app.get("/budgets/category/{category}", response_model=List[BudgetCreate])
def filter_budgets_by_category(category: str, db: Session = Depends(get_db)):
    return db.query(Budget).filter(Budget.category == category).all()


@app.get("/budgets/user/{user_id}", response_model=List[BudgetCreate])
def get_budgets_for_user(user_id: int, db: Session = Depends(get_db)):
    return db.query(Budget).filter(Budget.user_id == user_id).all()


@app.get("/budgets/total/{user_id}")
def get_total_budget(user_id: int, db: Session = Depends(get_db)):
    total_budget = db.query(func.sum(Budget.amount)).filter(Budget.user_id == user_id).scalar()
    return {"total_budget": total_budget}


@app.put("/budgets/extend/{budget_id}")
def extend_budget(budget_id: int, new_end_date: datetime, db: Session = Depends(get_db)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not db_budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    db_budget.end_date = new_end_date
    db.commit()
    return db_budget


@app.get("/budgets/exceeded/{budget_id}")
def check_budget_exceeded(budget_id: int, db: Session = Depends(get_db)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
    total_spent = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == db_budget.user_id, Transaction.category == db_budget.category).scalar()
    return {"budget_exceeded": total_spent > db_budget.amount}


@app.get("/analytics/spending/category/{category}")
def get_total_spending_by_category(category: str, db: Session = Depends(get_db)):
    total_spent = db.query(func.sum(Transaction.amount)).filter(Transaction.category == category).scalar()
    return {"total_spent": total_spent}


@app.get("/analytics/transactions/category/{category}")
def get_transactions_count_by_category(category: str, db: Session = Depends(get_db)):
    count = db.query(Transaction).filter(Transaction.category == category).count()
    return {"count": count}


@app.get("/analytics/budget/utilization/{budget_id}")
def get_budget_utilization(budget_id: int, db: Session = Depends(get_db)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id).first()
    total_spent = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == db_budget.user_id, Transaction.category == db_budget.category).scalar()
    utilization = total_spent / db_budget.amount if db_budget.amount > 0 else 0
    return {"utilization": utilization}


@app.get("/analytics/spending/monthly/{user_id}")
def get_monthly_spending_report(user_id: int, db: Session = Depends(get_db)):
    start_date = datetime.now().replace(day=1)
    end_date = (start_date + timedelta(days=31)).replace(day=1)
    monthly_spending = db.query(func.sum(Transaction.amount)).filter(Transaction.user_id == user_id, Transaction.date >= start_date, Transaction.date < end_date).scalar()
    return {"monthly_spending": monthly_spending}


@app.get("/analytics/spending/highest")
def get_highest_spending_category(db: Session = Depends(get_db)):
    result = db.query(Transaction.category, func.sum(Transaction.amount).label('total_spent')).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).first()
    return {"category": result[0], "total_spent": result[1]}
