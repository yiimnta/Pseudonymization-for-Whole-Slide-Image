from typing import TypeVar, Generic, Type, List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.future import select
from db.model import Case, Patient, Study, WSI

T = TypeVar("T")


class DAO(Generic[T]):
    def __init__(self, generic_cls: Type[T], db_session: Session, auto_commit=True):
        self._class = generic_cls
        self.session = db_session
        self.auto_commit = auto_commit

    async def create(self, obj: T) -> None:
        try:
            self.session.add(obj)
            if self.auto_commit:
                await self.commit()
        except Exception as e:
            print(str(e))
            return False
        return True

    async def get(self, id) -> T:
        return await self.session.get(self._class, id)

    async def get_case(self, id):
        a = await self.session.get(self._class, id)
        return a

    async def get_by_pseudo_id(self, pseudo_id) -> T:
        q = await self.session.execute(select(self._class).where(self._class.pseudo_id == pseudo_id))
        return q.scalars().first()

    async def get_alls(self) -> List[T]:
        q = await self.session.execute(select(self._class).order_by(self._class.id))
        return q.scalars().all()

    async def delete(self, obj: T):
        try:
            await self.session.delete(obj)
            if self.auto_commit:
                await self.commit()
        except Exception as e:
            print(str(e))
            return False
        return True

    async def delete_by_id(self, id):
        try:
            obj = await self.session.get(T, id)
            if obj is None:
                print('Could not found {0} has ID={1}'.format("Pseudonym", id))
                return False
            if self.auto_commit:
                await self.commit()
        except Exception as e:
            print(str(e))
            return False
        return True

    async def delete_all(self):
        try:
            await self.session.query(self._class).delete()
            if self.auto_commit:
                await self.commit()
        except Exception as e:
            print(str(e))
            return False
        return True

    async def commit(self):
        try:
            await self.session.commit()
        except Exception as e:
            print("Commit failed", str(e))
            await self.session.rollback()


class WSIDAO(DAO):

    def __init__(self, db_session: Session, auto_commit=True):
        super().__init__(WSI, db_session, auto_commit)


class CaseDAO(DAO):

    def __init__(self, db_session: Session, auto_commit=True):
        super().__init__(Case, db_session, auto_commit)

    async def get_by_id_with_slides(self, id) -> T:
        q = await self.session.execute(select(Case).where(Case.id == id).options(selectinload(Case.slides)))
        return q.scalars().first()

    async def get_by_pseudo_id_with_slides(self, pseudo_id) -> T:
        q = await self.session.execute(select(Case).where(Case.pseudo_id == pseudo_id).options(selectinload(Case.slides)))
        return q.scalars().first()


class PatientDAO(DAO):

    def __init__(self, db_session: Session, auto_commit=True):
        super().__init__(Patient, db_session, auto_commit)

    async def get_by_id_with_slides(self, id) -> T:
        q = await self.session.execute(select(Patient).where(Patient.id == id).options(selectinload(Patient.slides)))
        return q.scalars().first()

    async def get_by_pseudo_id_with_slides(self, pseudo_id) -> T:
        q = await self.session.execute(select(Patient).where(Patient.pseudo_id == pseudo_id).options(selectinload(Patient.slides)))
        return q.scalars().first()


class StudyDAO(DAO):

    def __init__(self, db_session: Session, auto_commit=True):
        super().__init__(Study, db_session, auto_commit)

    async def get_by_id_with_patients(self, id) -> T:
        q = await self.session.execute(select(Study).where(Study.id == id).options(selectinload(Study.patients)))
        return q.scalars().first()

    async def get_by_pseudo_id_with_patients(self, pseudo_id) -> T:
        q = await self.session.execute(select(Study).where(Study.pseudo_id == pseudo_id).options(selectinload(Study.patients)))
        return q.scalars().first()
