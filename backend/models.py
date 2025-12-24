from sqlalchemy import Column, Integer, String, Text, Date, Time, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class Cliente(Base):
    __tablename__ = "Customer"
    id = Column("internalId", Integer, primary_key=True, index=True)
    code = Column("Code", String(40), unique=True, index=True)
    nombre = Column("FantasyName", String(60))
    razon_social = Column("Name", String(60), nullable=False)
    ruc = Column("TaxRegNr", String(20), unique=True, index=True)
    contacto = Column("MainContactName", String(120))
    email = Column("Email", String(300), unique=True, index=True)
    estado = Column("Closed", String(50))
    support_hours = Column("SupportHours", Float, nullable=False, default=0.0)
    support_hours_consumed = Column("SupportHoursConsumed", Float, nullable=False, default=0.0)
    last_alert_level = Column("LastAlertLevel", Float, nullable=False, default=0.0)
    encargados = Column("Encargados", Text, nullable=True)
    
    actividades = relationship("Actividad", back_populates="cliente")
    proyectos = relationship("Proyecto", back_populates="cliente")
    personas = relationship("PersonOfCustomer", back_populates="cliente")
    cards = relationship("Card", back_populates="cliente")

class Proyecto(Base):
    __tablename__ = "Project"
    id = Column("internalId", Integer, primary_key=True, index=True)
    nombre = Column("Name", String(160), nullable=False)
    descripcion = Column("Comment", Text)
    fecha_inicio = Column("StartDate", Date)
    fecha_fin = Column("EndDate", Date)
    fecha_limite = Column("Deadline", Date)
    presupuesto = Column("Budget", Float)
    estado = Column("Status", String(50))
    
    cliente_id = Column("CustCode", Integer, ForeignKey("Customer.internalId"))
    cliente = relationship("Cliente", back_populates="proyectos")
    actividades = relationship("Actividad", back_populates="proyecto")

class Actividad(Base):
    __tablename__ = "Activity"
    id = Column("internalId", Integer, primary_key=True, index=True)
    titulo = Column("Comment", String(100))
    descripcion = Column("Detail", Text)
    prioridad = Column("Priority", Integer)
    tipo = Column("ActivityType", String(20))  # Used for billing type
    estado = Column("Status", Integer)
    fecha_creacion = Column("TransDate", Date)
    hora_inicio = Column("StartTime", Time)
    hora_fin = Column("EndTime", Time)
    user = Column("User", String(60))
    
    # Existing classification fields in database
    type_user = Column("TypeUser", Integer, nullable=True)  # Task type (Mapped to Int: 1=Prog, 2=Cons, etc.)
    activity_subtype = Column("ActivitySubType", String(50), nullable=True)  # Subtype
    overtime = Column("Overtime", Float, nullable=True)  # Hours to compensate
    
    cliente_id = Column("CustCode", Integer, ForeignKey("Customer.internalId"))
    cliente = relationship("Cliente", back_populates="actividades")
    proyecto_id = Column("Project", Integer, ForeignKey("Project.internalId"))
    proyecto = relationship("Proyecto")
    
    card_id = Column("CardId", Integer, ForeignKey("Cards.internalId"), nullable=True)
    card = relationship("Card", back_populates="actividades")

class PersonOfCustomer(Base):
    __tablename__ = "PersonOfCustomer"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String(50), unique=True, index=True, nullable=False)
    gmail = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    roll = Column(String(50), nullable=True)
    cliente_id = Column(Integer, ForeignKey("Customer.internalId"), nullable=True)
    cliente = relationship("Cliente", back_populates="personas")
    verification_code = Column(String(6), nullable=True)
    is_verified = Column(Boolean, default=False)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    status = Column(Integer, nullable=True, default=0)
    customername = Column(String(255), nullable=True)

class Card(Base):
    __tablename__ = "Cards"
    internalId = Column(Integer, primary_key=True, autoincrement=True)
    Status = Column(Integer, nullable=True)
    Code = Column(String(30), nullable=True)
    Trello = Column(Integer, nullable=True)
    Closed = Column(Boolean, nullable=True)
    attachFlag = Column(Boolean, nullable=True)
    syncVersion = Column(Integer, nullable=True)
    TrelloNumber = Column(Integer, nullable=True)
    HourCot = Column(Float, nullable=True)
    card_type = Column("Type", Integer, nullable=True) # Renamed to avoid conflict
    HourIns = Column(Float, nullable=True)
    Name = Column(String(1000), nullable=True)
    CardsType = Column(Integer, nullable=True)
    CustName = Column(String(150), nullable=True)
    LinkTrello = Column(String(1000), unique=True, nullable=True)
    HourCotCons = Column(Float, nullable=True)
    HourCotPrg = Column(Float, nullable=True)
    Comment = Column(Text, nullable=True)
    State = Column(String(20), nullable=True)
    StatusInvoice = Column(Integer, nullable=True)
    HourInv = Column(Float, nullable=True)
    Priority = Column(String(10), nullable=True)
    FinishDate = Column(Date, nullable=True)
    InvoiceNr = Column(Integer, nullable=True)
    User = Column(String(50), nullable=True)
    LimitDate = Column(Date, nullable=True)
    date_column = Column("Date", Date, nullable=True) # Renamed to avoid conflict
    time_column = Column("Time", Time, nullable=True) # Renamed to avoid conflict
    Problem = Column(String(20), nullable=True)
    ProblemDesc = Column(String(100), nullable=True)
    TransTime = Column(Time, nullable=True)
    SerNr = Column(Integer, unique=True, nullable=True)
    BaseRate = Column(Float, nullable=True)
    ToBaseRate1 = Column(Float, nullable=True)
    ShiftNr = Column(Integer, nullable=True)
    Invalid = Column(Boolean, nullable=True)
    CurrencyRate = Column(Float, nullable=True)
    Department = Column(String(10), nullable=True)
    SalesMan = Column(String(10), nullable=True)
    SalesGroup = Column(String(20), nullable=True)
    OriginType = Column(Integer, nullable=True)
    ToBaseRate2 = Column(Float, nullable=True)
    Printed = Column(Boolean, nullable=True)
    ToSerNr = Column(Integer, unique=True, nullable=True)
    Language = Column(String(10), nullable=True)
    Shift = Column(String(3), nullable=True)
    TransDate = Column(Date, nullable=True)
    OriginNr = Column(Integer, nullable=True)
    FormType = Column(String(10), nullable=True)
    Synchronized = Column(Boolean, nullable=True)
    Office = Column(String(10), nullable=True)
    Labels = Column(String(60), nullable=True)
    InvalidDate = Column(Date, nullable=True)
    WasApproved = Column(Boolean, nullable=True)
    Currency = Column(String(3), nullable=True)
    Computer = Column(String(5), nullable=True)
    FiscalTransType = Column(String(3), nullable=True)
    FromRate = Column(Float, nullable=True)
    Circuit = Column(String(10), nullable=True)
    PersonCode = Column(String(10), nullable=True)
    PersonName = Column(String(100), nullable=True)
    CardStatus = Column(Integer, nullable=True)
    AuthorizedBy = Column(String(60), nullable=True)
    RefStr = Column(String(60), nullable=True)
    OriginRowNr = Column(Integer, nullable=True)
    PrintFormat = Column(Integer, nullable=True)
    Module = Column(String(20), nullable=True)
    ModuleDesc = Column(String(100), nullable=True)
    UserCode = Column(String(10), nullable=True)
    Aproved = Column(Boolean, nullable=True)
    AprovedDate = Column(Date, nullable=True)
    HourInsPrg = Column(Float, nullable=True)
    HourInsCons = Column(Float, nullable=True)
    Label = Column(String(50), nullable=True)
    LocalityCode = Column(String(40), nullable=True)
    Province = Column(String(60), nullable=True)
    DistrictCode = Column(String(10), nullable=True)
    District = Column(String(60), nullable=True)
    ZipCode = Column(String(20), nullable=True)
    Locality = Column(String(60), nullable=True)
    City = Column(String(60), nullable=True)
    Address = Column(String(60), nullable=True)
    Country = Column(String(2), nullable=True)
    ProvinceCode = Column(String(10), nullable=True)
    Commission = Column(Boolean, nullable=True)
    AssignedCons = Column(String(10), nullable=True)
    AssignedPrg = Column(String(10), nullable=True)
    IncComission = Column(Boolean, nullable=True)
    IncEsquema = Column(Boolean, nullable=True)
    SerNrBoard = Column(String(30), nullable=True)
    LastModify = Column(Date, nullable=True)
    dateLastActivity = Column(String(30), nullable=True)
    StatusInvoiced = Column(Integer, nullable=True)
    StatusReceipt = Column(Integer, nullable=True)
    dateCommentLastActivity = Column(String(30), nullable=True)
    AdditionalHoursStatus = Column(String(50), nullable=True)
    state_last_changed_date = Column(DateTime, nullable=True)
    last_escalation_sent_date = Column(DateTime, nullable=True)
    assign = Column("Assign", String(60), nullable=True)
    TrelloId = Column(String(50), nullable=True)

    CustCode = Column(String(40), ForeignKey("Customer.Code"))
    cliente = relationship("Cliente", back_populates="cards", primaryjoin="Card.CustCode == Cliente.code")
    events = relationship("CardsEventRow", back_populates="card")
    attachments = relationship("TicketAttachment", back_populates="card")
    actividades = relationship("Actividad", back_populates="card")

class TicketAttachment(Base):
    __tablename__ = "TicketAttachments"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(1024), nullable=False)
    filesize = Column(Integer, nullable=False)
    mimetype = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    card_id = Column(Integer, ForeignKey("Cards.internalId"))
    card = relationship("Card", back_populates="attachments")

class CardsEventRow(Base):
    __tablename__ = "CardsEventRow"
    id = Column("internalId", Integer, primary_key=True, index=True)
    master_id = Column("masterId", Integer, ForeignKey("Cards.internalId"))
    comment = Column("Comment", Text)
    # Renamed date and time to avoid conflicts in this model too
    date_column = Column("Date", Date, nullable=True)
    time_column = Column("Time", Time, nullable=True)
    user = Column("User", String(50))
    
    card = relationship("Card", back_populates="events")

class SmtpSettings(Base):
    __tablename__ = "SmtpSettings"
    id = Column(Integer, primary_key=True, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    use_tls = Column(Boolean, default=True)
    use_ssl = Column(Boolean, default=False)

class CheckInOut(Base):
    __tablename__ = "CheckInOut"
    SerNr = Column(Integer, primary_key=True)
    user_name = Column("User", String(255))
    Office = Column(String(255))
    Computer = Column(String(255))
    Employee = Column(String(255), index=True)
    attendance_date = Column("Date", Date, index=True)
    attendance_time = Column(Time, index=True)
    BiometricClock = Column(String(255))
    transaction_date = Column("TransDate", Date)
    transaction_time = Column(Time, nullable=True)

class DepartmentManager(Base):
    __tablename__ = "DepartmentManager"
    id = Column("internalId", Integer, primary_key=True, index=True)
    rows = relationship("DepartmentManagerRow", back_populates="manager")

class DepartmentManagerRow(Base):
    __tablename__ = "DepartmentManagerRow"
    id = Column("internalId", Integer, primary_key=True, index=True)
    master_id = Column("masterId", Integer, ForeignKey("DepartmentManager.internalId"))
    department = Column("Department", String(100), nullable=False)
    in_charge_id = Column("InChargeId", Integer, ForeignKey("PersonOfCustomer.id"), nullable=False)
    in_charge_name = Column("InChargeName", String(100), nullable=False)
    manager = relationship("DepartmentManager", back_populates="rows")
    in_charge_person = relationship("PersonOfCustomer")

class AttentionFlowSettings(Base):
    __tablename__ = "AttentionFlowSettings"
    id = Column(Integer, primary_key=True, index=True)
    max_time_new = Column(Integer, default=0)
    max_time_pending = Column(Integer, default=0)
    max_time_testing = Column(Integer, default=0)
    max_time_waiting = Column(Integer, default=0)
    max_time_priority_low = Column(Integer, default=0)
    max_time_priority_medium = Column(Integer, default=0)
    max_time_priority_high = Column(Integer, default=0)
    max_time_priority_critical = Column(Integer, default=0)

class TrelloBoardData(Base):
    __tablename__ = "TrelloBoardData"
    internalId = Column(Integer, primary_key=True, autoincrement=True)
    Code = Column(String(100), unique=True, nullable=True)
    Data = Column(Text, nullable=True)
    attachFlag = Column(Boolean, nullable=True)
    syncVersion = Column(Integer, nullable=True)
    Closed = Column(Boolean, nullable=True)
    Time = Column(Time, nullable=True)
    Date = Column(Date, nullable=True)

class Board(Base):
    __tablename__ = "Boards"
    internalId = Column(Integer, primary_key=True, autoincrement=True)
    SerNr = Column(Integer, unique=True, nullable=True)
    ID = Column(String(300), nullable=True)
    Customer = Column(String(40), nullable=True)
    UpdateC = Column(Boolean, nullable=True)
    Department = Column(String(10), nullable=True)
    Closed = Column(Boolean, nullable=True)
    Assigned = Column(String(10), nullable=True)
    BoardType = Column(Integer, nullable=True)
    Name = Column(String(60), nullable=True)
    lists = relationship("BoardListRow", back_populates="board")

class BoardListRow(Base):
    __tablename__ = "BoardListsRow"
    internalId = Column(Integer, primary_key=True, autoincrement=True)
    masterId = Column(Integer, ForeignKey("Boards.internalId"), nullable=True)
    ID = Column(String(200), nullable=True)
    OpenStatus = Column(Integer, nullable=True)
    State = Column(String(20), nullable=True)
    Name = Column(String(200), nullable=True)
    board = relationship("Board", back_populates="lists")