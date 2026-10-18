from sqlmodel import Field, SQLModel


class AppMetadata(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
