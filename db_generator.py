from db.model import engine, Base
from db.config import SQLALCHEMY_DATABASE_URI
import asyncio
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database, drop_database
import platform

normal_engine = create_engine(SQLALCHEMY_DATABASE_URI)


class DB:

    @staticmethod
    async def generate():
        """
            create database and tables
            :return:
        """
        try:
            if not database_exists(normal_engine.url):
                create_database(normal_engine.url)

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        except Exception as ex:
            print("Exception during creating Database: " + str(ex))

    @staticmethod
    def drop():
        """
            drop database
        """
        try:
            if database_exists(normal_engine.url):
                # drop database
                drop_database(normal_engine.url)
            else:
                print("Exception during deleting Database: Database does not exist")

        except Exception as ex:
            print("Exception during deleting Database: " + str(ex))


# Windows has a problem with EventLoopPolicy
# It can make an async function "Asyncio Event Loop is Closed" when getting loop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DB.drop()
asyncio.run(DB.generate())
